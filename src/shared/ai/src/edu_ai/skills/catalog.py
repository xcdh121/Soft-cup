from edu_core.schemas.agent_orchestration import AgentName
from edu_core.schemas.agent_skills import SkillDefinition

from edu_ai.skills.registry import SkillRegistry


def build_skill_registry() -> SkillRegistry:
    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id="learner_evidence_collection", version="1.0", name="learner_evidence_collection",
        display_name="学习证据收集", description="汇总学习者画像、知识状态和近期练习形成可追溯证据。",
        applicable_agents=[AgentName.PROFILE, AgentName.KT, AgentName.DIAGNOSIS], execution_mode="hybrid",
        required_tools=["get_learner_profile", "get_knowledge_states"],
        optional_tools=["get_recent_practice_records"], max_tool_calls=4,
        quality_gates=["evidence_refs_present"], ui_visibility="details",
    ))
    registry.register(SkillDefinition(
        skill_id="root_cause_diagnosis", version="1.0", name="root_cause_diagnosis",
        display_name="学习问题根因诊断", description="基于知识状态、练习、先修图谱和教材证据识别可验证的薄弱点与根因。",
        applicable_agents=[AgentName.DIAGNOSIS], execution_mode="tool_loop",
        required_tools=["get_knowledge_states", "get_recent_practice_records"],
        optional_tools=["get_knowledge_graph", "search_course_materials"], max_tool_calls=6,
        quality_gates=["at_least_one_evidence", "low_evidence_caps_confidence"],
        fallback_skill_id="deterministic_root_cause_diagnosis", ui_visibility="details",
    ))
    registry.register(SkillDefinition(
        skill_id="deterministic_root_cause_diagnosis", version="1.0", name="deterministic_root_cause_diagnosis",
        display_name="规则根因诊断", description="工具或模型不可用时按知识掌握阈值生成保守诊断。",
        applicable_agents=[AgentName.DIAGNOSIS], execution_mode="deterministic",
        quality_gates=["low_evidence_caps_confidence"], ui_visibility="summary",
    ))
    registry.register(SkillDefinition(
        skill_id="learning_path_design", version="1.0", name="learning_path_design",
        display_name="个性化学习路径设计", description="结合真实知识状态、先修关系与时间约束生成可验收学习路径。",
        applicable_agents=[AgentName.PLANNER], execution_mode="hybrid",
        required_tools=["get_knowledge_states", "get_knowledge_graph"],
        optional_tools=["get_learner_profile"], max_tool_calls=5,
        quality_gates=["prerequisites_valid", "steps_have_acceptance_criteria"],
        fallback_skill_id="deterministic_learning_path_design", ui_visibility="details",
    ))
    registry.register(SkillDefinition(
        skill_id="deterministic_learning_path_design", version="1.0", name="deterministic_learning_path_design",
        display_name="规则学习路径设计", description="模型不可用时使用稳定规则规划路径。",
        applicable_agents=[AgentName.PLANNER], execution_mode="deterministic", ui_visibility="summary",
    ))
    return registry
