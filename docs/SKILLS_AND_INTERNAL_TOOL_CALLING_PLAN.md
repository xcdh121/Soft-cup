# Skill 与 Internal Tool Calling 改造方案

## 1. 目标与结论

本方案用于把当前“Supervisor 按固定顺序调用多个规则模块”的实现，升级为可观察、可约束、可审计的工具型多智能体系统。

核心关系如下：

```text
Supervisor 选择 Agent
Agent 选择或执行 Skill
Skill 按教学策略组织一个或多个 Tool
Tool 调用项目内部 Service / Database
```

三个概念的边界：

- `Agent`：负责一个长期角色，例如诊断、规划、资源生成。
- `Skill`：可复用的教学能力和执行策略，例如根因诊断、学习路径设计。
- `Tool`：一次可验证的原子操作，例如读取知识状态、搜索教材、创建测验草稿。

MVP 不引入 MCP。内部数据库和 Service 先通过 Internal Tool Calling 暴露；以后连接 LMS、外部题库或网盘时，再将外部能力接入 MCP。

## 2. 设计原则

1. 不为每个 Skill 新建一个 Agent。一个 Agent 可以组合多个 Skill，一个 Skill 也可以被多个 Agent 复用。
2. Skill 定义存放在代码或 YAML 中，运行记录进入数据库。MVP 不做动态 Skill 编辑后台。
3. Tool 参数必须经过 Pydantic 校验；`user_id`、权限和运行上下文只能由服务器注入，模型不能指定。
4. 读取工具可以自动执行；生成和写入工具按风险等级决定是否需要确认。
5. 不保存或展示模型完整思维链，只记录任务摘要、工具调用、证据、结果和置信度。
6. 每次运行必须有最大步数、超时、幂等键和审计记录，禁止无限工具循环。
7. 没有工具调用能力的模型必须回退到确定性执行路径。

## 3. 建议代码结构

```text
src/shared/ai/src/edu_ai/
├── agents/orchestration/
│   ├── supervisor.py
│   ├── diagnosis_agent.py
│   ├── planner_agent.py
│   └── resource_agent.py
├── skills/
│   ├── base.py
│   ├── registry.py
│   ├── evidence_collection.py
│   ├── root_cause_diagnosis.py
│   ├── learning_path_design.py
│   ├── grounded_resource_generation.py
│   └── intervention_verification.py
└── internal_tools/
    ├── base.py
    ├── registry.py
    ├── runner.py
    ├── learner.py
    ├── knowledge.py
    ├── practice.py
    ├── retrieval.py
    ├── resources.py
    └── learning_paths.py

src/shared/core/src/edu_core/schemas/
├── agent_skills.py
└── internal_tools.py
```

现有 `edu_ai/tools` 主要服务内容生成，可逐步包装为 `internal_tools`，不要求一次搬迁。

## 4. Skill 字段设计

### 4.1 SkillDefinition

Skill 定义建议使用 Pydantic，定义本身不进入数据库：

```python
class SkillDefinition(BaseModel):
    skill_id: str
    version: str
    name: str
    display_name: str
    description: str
    status: Literal["active", "experimental", "disabled"] = "active"

    applicable_agents: list[AgentName]
    execution_mode: Literal["deterministic", "llm", "tool_loop", "hybrid"]
    trigger_conditions: list[str] = []

    input_schema: dict
    output_schema: dict
    required_tools: list[str] = []
    optional_tools: list[str] = []

    prompt_template: str | None = None
    max_tool_calls: int = 6
    timeout_seconds: int = 60
    quality_gates: list[str] = []
    fallback_skill_id: str | None = None

    ui_visibility: Literal["hidden", "summary", "details"] = "summary"
    tags: list[str] = []
```

字段说明：

| 字段 | 用途 |
|---|---|
| `skill_id` | 稳定标识，例如 `root_cause_diagnosis` |
| `version` | 固定本次运行所用能力版本，便于复现和评测 |
| `execution_mode` | 区分规则 Skill、单次 LLM、工具循环和混合流程 |
| `trigger_conditions` | Supervisor 或 Agent 选择 Skill 的条件 |
| `required_tools` | 缺少其中任何工具时不得正常运行 |
| `optional_tools` | 可增强结果，但缺少时允许降级 |
| `quality_gates` | 输出前必须通过的检查，例如证据数和先修约束 |
| `fallback_skill_id` | LLM 或工具失败时使用的规则 Skill |
| `ui_visibility` | 控制前端是否展示该 Skill |

不要在 Skill 中保存用户数据、数据库连接、API Key 或具体 `user_id`。

### 4.2 SkillExecution

每次执行 Skill 都需要运行记录，建议新增 `skill_executions` 表：

```python
class SkillExecution(Base):
    id: str
    run_id: str
    agent_name: str
    skill_id: str
    skill_version: str
    status: str

    input_summary: dict
    output_summary: dict
    output_artifact_key: str | None
    confidence: float | None

    fallback_used: bool
    fallback_reason: str | None
    error_code: str | None
    error_message: str | None

    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
```

`input_summary` 只保存字段数量、数据来源 ID 和必要摘要，不复制完整教材、聊天或敏感用户数据。

## 5. Tool 字段设计

### 5.1 ToolDefinition

```python
class ToolDefinition(BaseModel):
    tool_name: str
    version: str = "1.0"
    display_name: str
    description: str
    category: Literal["learner", "knowledge", "practice", "retrieval", "generation", "planning"]

    input_model: type[BaseModel]
    output_model: type[BaseModel]

    allowed_agents: list[AgentName]
    risk_level: Literal["read", "generate", "write", "destructive"]
    approval_policy: Literal["never", "conditional", "always"]

    timeout_seconds: int = 15
    idempotent: bool = True
    audit_enabled: bool = True
    result_visibility: Literal["hidden", "summary", "details"] = "summary"
```

Tool 描述必须说明“什么时候使用”，不能只写函数含义。例如：

```text
查询当前学生在指定项目中的知识点掌握度、置信度和趋势。
当诊断或规划需要真实掌握证据时使用；不要用它修改掌握度。
```

### 5.2 ToolExecutionContext

以下字段由服务器注入，不出现在模型可填写的 Tool Schema 中：

```python
class ToolExecutionContext(BaseModel):
    run_id: str
    request_id: str
    user_id: str
    project_id: str
    agent_name: AgentName
    skill_id: str
    user_roles: list[str]
    locale: str = "zh-CN"
```

特别注意：模型只能传 `knowledge_point_ids`、`limit` 等业务参数，不能传 `user_id`，否则存在越权读取其他学生数据的风险。

### 5.3 ToolCallRequest 与 ToolCallResult

```python
class ToolCallRequest(BaseModel):
    call_id: str
    tool_name: str
    arguments: dict
    idempotency_key: str | None = None


class ToolCallResult(BaseModel):
    call_id: str
    tool_name: str
    status: Literal["completed", "failed", "denied", "timeout"]
    data: dict | list | None = None
    summary: str
    evidence_refs: list[AgentEvidence] = []
    error_code: str | None = None
    retryable: bool = False
    duration_ms: int
```

返回给模型的 `data` 应当有大小限制。例如练习记录默认最多 50 条，教材检索默认最多 10 个片段，禁止把整份 PDF 放入工具结果。

### 5.4 ToolCall 数据库表

建议新增 `agent_tool_calls`：

```python
class AgentToolCall(Base):
    id: str
    run_id: str
    skill_execution_id: str | None
    agent_name: str
    skill_id: str | None
    tool_name: str
    tool_version: str

    status: str
    risk_level: str
    approval_status: str
    arguments: dict
    result_summary: dict
    evidence_refs: list[dict]

    idempotency_key: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime
    completed_at: datetime | None
    duration_ms: int | None
```

安全要求：

- `arguments` 入库前进行字段级脱敏。
- 不记录 API Key、Authorization Header、完整教材内容和模型隐式推理。
- 对生成和写操作建立唯一 `idempotency_key`，防止重试产生多份资源。
- `error_message` 面向后台排错；前端只使用安全的 `result_summary`。

## 6. Agent 协议需要增加的字段

在现有 `AgentResult` 上增加：

```python
skill_executions: list[SkillExecutionSummary] = []
tool_call_ids: list[str] = []
input_artifact_keys: list[str] = []
output_artifact_keys: list[str] = []
```

新增事件类型：

```python
SKILL_STARTED
SKILL_COMPLETED
SKILL_FAILED
TOOL_CALL_STARTED
TOOL_CALL_COMPLETED
TOOL_CALL_FAILED
TOOL_APPROVAL_REQUIRED
```

事件 payload 使用统一字段：

```json
{
  "skill_id": "root_cause_diagnosis",
  "skill_display_name": "学习问题根因诊断",
  "tool_call_id": "call_xxx",
  "tool_name": "get_recent_practice_records",
  "tool_display_name": "读取近期练习记录",
  "phase": "completed",
  "result_summary": "读取 20 条记录，发现 6 次同类错误",
  "evidence_count": 6,
  "duration_ms": 184,
  "ui_visibility": "details"
}
```

## 7. Tool Runner 与调用循环

### 7.1 ToolRunner 职责

所有工具必须经过统一 `ToolRunner`，Agent 不应直接调用 Service：

```text
校验工具是否存在
→ 校验 Agent 白名单
→ 校验用户与项目权限
→ 校验参数 Schema
→ 判断是否需要确认
→ 生成或校验幂等键
→ 执行超时控制
→ 调用内部 Service
→ 过滤和压缩结果
→ 写审计记录
→ 发送 AgentEvent
```

### 7.2 受控工具循环

```python
for step in range(skill.max_tool_calls):
    response = await llm_with_tools.ainvoke(messages)
    if not response.tool_calls:
        return validate_final_output(response)

    for call in response.tool_calls:
        result = await tool_runner.execute(call, execution_context)
        messages.append(tool_result_message(result))

raise ToolLoopLimitExceeded(skill.skill_id)
```

还要设置：

- 单工具超时；
- Skill 总超时；
- 最大 Tool Call 数；
- 同一参数重复调用检测；
- 写工具每轮最多一次；
- 失败是否允许重试；
- 最终输出 Pydantic 校验。

现有 LangChain `BaseChatModel` 可以通过 `bind_tools()` 接入原生 Tool Calling。模型不支持时，执行 `fallback_skill_id` 指定的确定性 Skill。

## 8. 第一批 Skill

### 8.1 `learner_evidence_collection`

- 使用 Agent：ProfileAgent、KTAgent、DiagnosisAgent
- 执行模式：`hybrid`
- 必需工具：`get_learner_profile`、`get_knowledge_states`
- 可选工具：`get_recent_practice_records`、`get_feedback_summary`
- 输出：画像摘要、知识状态摘要、证据引用、数据缺口

### 8.2 `root_cause_diagnosis`

- 使用 Agent：DiagnosisAgent
- 执行模式：`tool_loop`
- 必需工具：`get_knowledge_states`、`get_recent_practice_records`
- 可选工具：`get_knowledge_graph`、`search_course_materials`
- 质量门：至少一个真实 evidence；低证据时不得输出高置信度根因
- 输出：薄弱点、根因候选、证据、置信度、建议补测项

### 8.3 `learning_path_design`

- 使用 Agent：PlannerAgent
- 执行模式：`hybrid`
- 必需工具：`get_knowledge_states`、`get_knowledge_graph`
- 可选工具：`get_learner_profile`、`get_available_resources`、`get_previous_learning_paths`
- 质量门：先修关系正确、总时长满足约束、每一步有目标和验收条件
- 输出：学习路径草稿

### 8.4 `grounded_resource_generation`

- 使用 Agent：ResourceAgent
- 执行模式：`tool_loop`
- 必需工具：`search_course_materials`
- 可选工具：`generate_quiz_draft`、`generate_note_draft`、`generate_flashcards_draft`、`generate_mind_map_draft`
- 质量门：生成内容必须关联知识点和材料证据
- 输出：资源草稿列表

### 8.5 `intervention_verification`

- 使用 Agent：后续新增 VerifierAgent，或先由 Supervisor 调用
- 执行模式：`hybrid`
- 工具：只读工具
- 质量门：诊断、推荐和路径之间不存在矛盾
- 输出：通过、退回补证据、退回重新规划

## 9. 第一批 Internal Tools

优先实现只读工具：

| Tool | 内部实现 | 风险 |
|---|---|---|
| `get_learner_profile` | `LearnerProfileService.get_profile` | read |
| `get_knowledge_states` | `KnowledgeStateService.list_states` | read |
| `get_recent_practice_records` | `PracticeService` 或受限查询 Service | read |
| `get_knowledge_graph` | Course/KnowledgeState Service | read |
| `search_course_materials` | `SearchService.search_documents` | read |
| `get_feedback_summary` | orchestration feedback aggregator | read |
| `get_available_resources` | ResourcePackage Service | read |

第二批实现生成工具：

| Tool | 行为 | 风险/确认 |
|---|---|---|
| `generate_diagnostic_quiz_draft` | 生成诊断题草稿 | generate / 不确认 |
| `generate_note_draft` | 生成笔记草稿 | generate / 不确认 |
| `generate_flashcards_draft` | 生成闪卡草稿 | generate / 不确认 |
| `draft_learning_path` | 生成学习路径草稿 | generate / 不确认 |
| `publish_learning_path` | 发布或替换正式路径 | write / 条件确认 |
| `update_learner_profile` | 修订画像并记录 revision | write / 条件确认 |

MVP 不开放删除类工具给模型。

## 10. 现有 Agent 的改造方式

### SupervisorAgent

- 继续负责目标级路由，不直接访问数据库。
- 路由计划增加 `selected_skills`。
- 根据 Skill 的输入就绪度、置信度和失败结果决定补证据或降级。
- 第一阶段保持规则路由，避免同时改成完全自主 Supervisor。

### ProfileAgent / KTAgent

- 第一阶段仍以确定性逻辑为主。
- 从直接读取 `AgentContextData` 改成使用只读 Tool，验证工具基础设施。
- 输出必须包含 evidence refs 和数据新鲜度。

### DiagnosisAgent

- 从“选择第一个薄弱知识点”升级为 `root_cause_diagnosis` Skill。
- 允许查询练习、知识图谱和教材证据。
- 证据不足时输出补测建议，不伪造群体模式。

### PlannerAgent

- 使用 `learning_path_design` Skill。
- 先通过 Tool 获取真实知识状态、先修图和时间约束，再调用 LLM。
- 输出经过规则校验；失败继续使用现有 rule fallback。

### ResourceAgent

- 将当前直接 Service 分支逐步包装成生成工具。
- Agent 选择资源类型，ToolRunner 负责权限、幂等和审计。

## 11. 前端是否展示 Skill

结论：需要展示，但不应把 Skill 当成与 Agent 同级的主导航或独立聊天角色。

推荐三层显示：

1. 主流程显示 Agent：`画像智能体 → 知识追踪智能体 → 诊断智能体 → 规划智能体`。
2. Agent 卡片显示 Skill 标签：`诊断智能体 · 学习问题根因诊断`。
3. 展开 Agent 卡片后显示 Tool 行动记录和证据。

示例：

```text
✓ 诊断智能体                         1.8 秒
  使用能力：学习问题根因诊断
  结论：主要障碍是递归状态定义不稳定
  置信度：82%

  查看执行详情
  ├─ 查询知识状态：读取 12 个知识点
  ├─ 读取近期练习：发现 6 次同类错误
  └─ 检索课程资料：找到 3 个相关证据片段
```

面向学生使用中文的 `display_name`，不要直接显示 `root_cause_diagnosis`、JSON Schema、Prompt、Token 或完整参数。

前端建议增加一个“协作详情”抽屉：

- 默认折叠，只显示参与 Agent 数量和运行状态；
- 展开后显示 Agent、Skill、Tool 的层级；
- 跳过、fallback、低置信度使用黄色提示；
- Tool 结果只显示摘要和证据数量；
- 比赛演示模式可默认展开，正常学生模式默认折叠。

不应展示：

- 模型完整思维链；
- 系统 Prompt；
- API Key 和内部错误堆栈；
- 未脱敏的 Tool 参数；
- 未执行的全部 Skill 清单。

## 12. API 与前端类型

建议增加统一运行详情接口：

```text
GET /api/v1/agent-runs/{run_id}
GET /api/v1/agent-runs/{run_id}/events
GET /api/v1/agent-runs/{run_id}/skill-executions
GET /api/v1/agent-runs/{run_id}/tool-calls
```

前端核心类型：

```ts
type SkillExecutionSummary = {
  id: string
  agentName: string
  skillId: string
  displayName: string
  version: string
  status: 'running' | 'completed' | 'failed'
  summary: string
  confidence: number | null
  fallbackUsed: boolean
  durationMs: number | null
  toolCalls: ToolCallSummary[]
}

type ToolCallSummary = {
  id: string
  toolName: string
  displayName: string
  status: 'running' | 'completed' | 'failed' | 'denied' | 'timeout'
  resultSummary: string
  evidenceCount: number
  durationMs: number | null
}
```

现有 `AgentProgressPanel` 可以扩展为：

```text
AgentCollaborationPanel
├── AgentStepCard
│   ├── SkillBadge
│   ├── ToolCallTimeline
│   └── EvidenceSummary
└── FallbackNotice
```

## 13. 实施阶段

### Phase 0：先修复数据链路

1. `_load_context()` 接入 learner profile、knowledge states、knowledge points。
2. 修复 learning path 接口没有运行 Planner 的问题。
3. 增加服务级闭环测试。

### Phase 1：Tool 基础设施

1. 建立 ToolDefinition、Registry、Runner 和运行协议。
2. 实现 5 个只读 Tool。
3. 增加 `agent_tool_calls` 表和事件。
4. 先让 DiagnosisAgent 使用受控 Tool Calling。

### Phase 2：Skill 基础设施

1. 建立 SkillDefinition、Registry、Runner。
2. 实现前三个核心 Skill。
3. 增加 `skill_executions` 表。
4. AgentResult 和 trace 关联 Skill 与 Tool。

### Phase 3：生成与写工具

1. 包装现有 quiz、note、flashcard、mind map、learning path Service。
2. 增加幂等、确认、超时和重试。
3. 接入 Verifier 或 quality gates。

### Phase 4：前端比赛展示

1. 抽取通用 `AgentCollaborationPanel`。
2. 在诊断、资源、学习路径页面复用。
3. 显示 Agent → Skill → Tool → Evidence 层级。
4. 增加比赛演示模式。

## 14. 验收标准

- DiagnosisAgent 能自主选择至少 3 个只读 Tool，并在最大步数内停止。
- 每个 Tool Call 都有权限校验、参数校验、超时和审计记录。
- 模型不能通过 Tool 参数读取其他用户或项目的数据。
- 生成工具重试不会重复创建资源。
- 不支持 Tool Calling 的模型会稳定回退。
- 前端能实时显示 Agent、Skill 和 Tool 的结构化状态。
- 前端不泄露思维链、Prompt、密钥或敏感参数。
- 诊断结论可以追溯到练习、知识状态或教材证据。
- 单元测试覆盖 Registry、权限、Schema、超时、幂等和循环上限。
- 集成测试覆盖 diagnosis → recommendations → learning path 完整链路。

## 15. MVP 范围建议

比赛阶段最小但足够有说服力的范围是：

1. 3 个 Skill：证据收集、根因诊断、学习路径设计。
2. 5 个只读 Tool：画像、知识状态、练习记录、知识图谱、教材检索。
3. 2 个生成 Tool：诊断测验草稿、学习路径草稿。
4. 1 个通用协作面板，显示 Agent → Skill → Tool → Evidence。
5. 不实现动态 Skill 管理后台、不开放删除工具、不接 MCP。

这一范围已经足以证明系统不是简单的多提示词串行调用，同时保持可在比赛周期内完成和验证。
