from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from edu_core.schemas.agent_orchestration import AgentContextData, AgentEvidence, AgentName
from edu_core.schemas.internal_tools import ToolDefinition

from edu_ai.internal_tools.base import InternalToolOutput
from edu_ai.internal_tools.registry import ToolRegistry


READ_AGENTS = [AgentName.PROFILE, AgentName.KT, AgentName.DIAGNOSIS, AgentName.PLANNER]


class EmptyInput(BaseModel):
    pass


class KnowledgeStateInput(BaseModel):
    knowledge_point_ids: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(50, ge=1, le=50)


class PracticeInput(BaseModel):
    knowledge_point_ids: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(20, ge=1, le=50)


class KnowledgeGraphInput(BaseModel):
    knowledge_point_ids: list[str] = Field(default_factory=list, max_length=50)


class SearchMaterialsInput(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    limit: int = Field(5, ge=1, le=10)


class DiagnosticQuizInput(BaseModel):
    knowledge_point_ids: list[str] = Field(min_length=1, max_length=10)
    question_count: int = Field(5, ge=1, le=10)


class LearningPathDraftInput(BaseModel):
    knowledge_point_ids: list[str] = Field(min_length=1, max_length=20)
    available_minutes: int = Field(60, ge=15, le=1440)


class ProfileOutput(BaseModel):
    profile: dict[str, Any] | None


class ItemsOutput(BaseModel):
    items: list[dict[str, Any]]


class GraphOutput(BaseModel):
    nodes: list[dict[str, Any]]
    edges: list[dict[str, Any]]


class DraftOutput(BaseModel):
    draft: dict[str, Any]


def build_context_tool_registry(context_data: AgentContextData) -> ToolRegistry:
    """Build read-only tools over a server-loaded, ownership-scoped context snapshot."""
    registry = ToolRegistry()

    def profile(_args, _context):
        profile_data = context_data.learner_profile
        refs = []
        if profile_data:
            refs.append(AgentEvidence(source_type="learner_profile", source_id=str(profile_data.get("id", "current"))))
        return InternalToolOutput(
            data={"profile": profile_data},
            summary="已读取学习者画像。" if profile_data else "当前没有学习者画像。",
            evidence_refs=refs,
        )

    registry.register(
        ToolDefinition(
            tool_name="get_learner_profile", display_name="读取学习者画像",
            description="当诊断或规划需要学习偏好、目标与时间约束时读取当前项目学习者画像；不能用于修改画像。",
            category="learner", input_model=EmptyInput, output_model=ProfileOutput,
            allowed_agents=READ_AGENTS, risk_level="read", approval_policy="never",
        ), profile,
    )

    def states(args: KnowledgeStateInput, _context):
        wanted = set(args.knowledge_point_ids)
        items = [item for item in context_data.knowledge_states if not wanted or str(item.get("knowledge_point_id", item.get("id"))) in wanted][:args.limit]
        refs = [AgentEvidence(source_type="knowledge_state", source_id=str(item.get("knowledge_point_id", item.get("id", "unknown")))) for item in items]
        return InternalToolOutput(data={"items": items}, summary=f"读取 {len(items)} 个知识状态。", evidence_refs=refs)

    registry.register(
        ToolDefinition(
            tool_name="get_knowledge_states", display_name="查询知识状态",
            description="当诊断或规划需要真实掌握度、置信度和趋势时读取当前学生知识状态；不能用于修改掌握度。",
            category="knowledge", input_model=KnowledgeStateInput, output_model=ItemsOutput,
            allowed_agents=READ_AGENTS, risk_level="read", approval_policy="never",
        ), states,
    )

    def practice(args: PracticeInput, _context):
        wanted = set(args.knowledge_point_ids)
        items = [item for item in context_data.practice_records if not wanted or str(item.get("knowledge_point_id")) in wanted][:args.limit]
        refs = [AgentEvidence(source_type="practice_record", source_id=str(item.get("id", "unknown"))) for item in items]
        wrong = sum(item.get("was_correct") is False for item in items)
        return InternalToolOutput(data={"items": items}, summary=f"读取 {len(items)} 条近期练习，其中 {wrong} 条错误。", evidence_refs=refs)

    registry.register(
        ToolDefinition(
            tool_name="get_recent_practice_records", display_name="读取近期练习",
            description="当诊断需要核验重复错误、作答表现和新鲜度时读取当前项目近期练习，最多返回 50 条。",
            category="practice", input_model=PracticeInput, output_model=ItemsOutput,
            allowed_agents=[AgentName.KT, AgentName.DIAGNOSIS, AgentName.PLANNER], risk_level="read", approval_policy="never",
        ), practice,
    )

    def graph(args: KnowledgeGraphInput, _context):
        wanted = set(args.knowledge_point_ids)
        nodes = [item for item in context_data.knowledge_points if not wanted or str(item.get("id", item.get("knowledge_point_id"))) in wanted]
        ids = {str(item.get("id", item.get("knowledge_point_id"))) for item in nodes}
        edges = []
        for node in nodes:
            target = str(node.get("id", node.get("knowledge_point_id")))
            for source in node.get("prerequisite_ids", node.get("prerequisites", [])) or []:
                source_id = str(source.get("id")) if isinstance(source, dict) else str(source)
                if not wanted or source_id in ids:
                    edges.append({"source": source_id, "target": target, "type": "prerequisite"})
        refs = [AgentEvidence(source_type="knowledge_point", source_id=item) for item in ids]
        return InternalToolOutput(data={"nodes": nodes, "edges": edges}, summary=f"读取 {len(nodes)} 个知识点和 {len(edges)} 条先修关系。", evidence_refs=refs)

    registry.register(
        ToolDefinition(
            tool_name="get_knowledge_graph", display_name="读取知识图谱",
            description="当根因诊断或学习路径需要检查薄弱点的先修依赖时读取当前课程知识图谱。",
            category="knowledge", input_model=KnowledgeGraphInput, output_model=GraphOutput,
            allowed_agents=[AgentName.DIAGNOSIS, AgentName.PLANNER], risk_level="read", approval_policy="never",
        ), graph,
    )

    def materials(args: SearchMaterialsInput, _context):
        query = args.query.casefold()
        terms = [term for term in query.split() if term]
        candidates = []
        for item in context_data.documents:
            searchable = " ".join(str(item.get(key, "")) for key in ("title", "file_name", "summary", "content")).casefold()
            if not terms or any(term in searchable for term in terms):
                candidates.append({
                    "id": item.get("id"), "title": item.get("title", item.get("file_name", "课程资料")),
                    "snippet": str(item.get("summary", item.get("content", "")))[:500],
                })
        items = candidates[:args.limit]
        refs = [AgentEvidence(source_type="course_material", source_id=str(item.get("id", "unknown"))) for item in items]
        return InternalToolOutput(data={"items": items}, summary=f"检索到 {len(items)} 个相关材料片段。", evidence_refs=refs)

    registry.register(
        ToolDefinition(
            tool_name="search_course_materials", display_name="检索课程资料",
            description="当诊断结论需要教材依据时，在当前项目已授权资料摘要中检索相关片段；不要传入整份文档。",
            category="retrieval", input_model=SearchMaterialsInput, output_model=ItemsOutput,
            allowed_agents=[AgentName.DIAGNOSIS, AgentName.RESOURCE, AgentName.PLANNER], risk_level="read", approval_policy="never",
        ), materials,
    )

    def diagnostic_quiz(args: DiagnosticQuizInput, _context):
        questions = [
            {
                "id": f"draft-question-{index + 1}",
                "knowledge_point_id": args.knowledge_point_ids[index % len(args.knowledge_point_ids)],
                "prompt": "请解释该知识点并完成一个最小示例。",
                "status": "draft",
            }
            for index in range(args.question_count)
        ]
        return InternalToolOutput(
            data={"draft": {"type": "diagnostic_quiz", "questions": questions}},
            summary=f"已生成 {len(questions)} 道诊断题草稿。",
            evidence_refs=[AgentEvidence(source_type="knowledge_point", source_id=item) for item in args.knowledge_point_ids],
        )

    registry.register(
        ToolDefinition(
            tool_name="generate_diagnostic_quiz_draft", display_name="生成诊断测验草稿",
            description="当现有证据不足以确认根因时，为当前薄弱知识点生成未发布的补测草稿。",
            category="generation", input_model=DiagnosticQuizInput, output_model=DraftOutput,
            allowed_agents=[AgentName.DIAGNOSIS], risk_level="generate", approval_policy="never",
        ), diagnostic_quiz,
    )

    def learning_path_draft(args: LearningPathDraftInput, _context):
        minutes = max(10, args.available_minutes // len(args.knowledge_point_ids))
        steps = [
            {
                "step_no": index + 1, "knowledge_point_id": point_id,
                "objective": "理解并能独立应用该知识点。",
                "acceptance_condition": "完成针对性练习且正确率达到 80%。",
                "estimated_minutes": minutes, "status": "draft",
            }
            for index, point_id in enumerate(args.knowledge_point_ids)
        ]
        return InternalToolOutput(
            data={"draft": {"type": "learning_path", "steps": steps}},
            summary=f"已生成包含 {len(steps)} 个步骤的学习路径草稿。",
            evidence_refs=[AgentEvidence(source_type="knowledge_point", source_id=item) for item in args.knowledge_point_ids],
        )

    registry.register(
        ToolDefinition(
            tool_name="draft_learning_path", display_name="生成学习路径草稿",
            description="当规划智能体已获得知识状态和先修关系后，生成未发布、可校验的学习路径草稿。",
            category="planning", input_model=LearningPathDraftInput, output_model=DraftOutput,
            allowed_agents=[AgentName.PLANNER], risk_level="generate", approval_policy="never",
        ), learning_path_draft,
    )
    return registry
