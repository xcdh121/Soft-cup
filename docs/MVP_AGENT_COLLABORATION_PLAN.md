# MVP 智能体协同改造方案

## 1. 目标

当前项目已经具备多 Agent 串行执行能力，但还缺少规则化调度、稳定降级、反馈回流和回归验证能力。

本次改造目标不是继续增加 Agent，而是把现有协同层升级为：

1. 能根据上下文决定执行路径
2. 能在信息不足时安全降级
3. 能把关键反馈整理成下一轮输入
4. 能通过最小 harness 做回归验证

## 2. 本次范围

本方案只聚焦协同层，不展开数据库和 KT 底层模型设计。

本方案默认遵循需求文档和现有编排文档中的边界约束：

1. Agent 必须读取共享上下文，不能只靠单一 prompt 或私有变量做判断
2. 编排层优先复用已有业务接口或 service 读取事实数据
3. 不允许为了协同层方便而随意改动已有对外接口
4. 如确实存在缺口，只新增最小必要接口，并与现有需求文档保持一致

本次覆盖：

1. `SupervisorAgent` 调度规则
2. Agent 跳过与 fallback 规则
3. 最小输出协议补充
4. 反馈摘要规则
5. 最小 harness 方案

本次不覆盖：

1. KT 表结构与算法细节
2. 群体洞察底层数据建设
3. 新增更多业务 Agent
4. 复杂在线学习或推荐策略优化

## 3. 上下文读取与接口边界

### 3.1 Agent 必须读取的上下文

MVP 阶段每个 Agent 都必须基于统一上下文工作，不能绕开 `AgentRunContext` 自行拼装私有状态。

建议 `SupervisorAgent` 在执行前统一装配以下上下文字段：

1. `learner_profile`
2. `knowledge_states`
3. `practice_records`
4. `collective_insights`
5. `generated_resources`
6. `recent_feedback_summary`
7. 必要时补充 `evaluation_report_summary`

使用原则：

1. `ProfileAgent` 至少读取 `learner_profile` 和 `recent_feedback_summary`
2. `KTAgent` 至少读取 `knowledge_states`、`practice_records` 和 `recent_feedback_summary`
3. `DiagnosisAgent` 至少读取 `learner_profile`、`knowledge_states`、`practice_records`
4. `ResourceAgent` 至少读取 diagnosis 结果、`learner_profile`、`generated_resources`
5. `PlannerAgent` 至少读取 diagnosis 结果、recommendations 和 `recent_feedback_summary`

结论约束：

1. Agent 的结论必须能回溯到上下文字段或上游 artifact
2. 不允许只根据单次自由文本生成强结论
3. 没有读到必要上下文时，应降级或返回 `insufficient_evidence`

### 3.2 接口边界

参考需求文档和现有编排文档，协同层应优先复用已有接口或 service，不直接操作底层表。

优先复用的接口：

1. `GET /api/v1/projects/{project_id}/learner-profile`
2. `PATCH /api/v1/projects/{project_id}/learner-profile`
3. `GET /api/v1/projects/{project_id}/knowledge-states`
4. `GET /api/v1/projects/{project_id}/knowledge-states/{knowledge_point_id}`
5. `GET /api/v1/projects/{project_id}/diagnosis/{diagnosis_id}/trace`
6. `POST /api/v1/projects/{project_id}/recommendations/{recommendation_id}/feedback`
7. `GET /api/v1/projects/{project_id}/evaluation-reports/latest`

约束：

1. 不因为协同层改造而重命名已有接口
2. 不改变已有接口核心语义
3. 不新增“仅供某个 Agent 私用”的对外接口
4. 优先在 `SupervisorAgent` 或 service 层做上下文装配，而不是把接口改碎

## 4. Supervisor 改造方案

建议把当前 `SupervisorAgent` 明确拆成 3 个阶段：

1. `Preflight`
2. `Route Decision`
3. `Execution`

### 4.1 Preflight

`Preflight` 负责检查本轮可用输入，不做业务结论，只做可运行性判断。

建议检查以下输入：

1. `learner_profile`
2. `knowledge_states`
3. `practice_records`
4. `collective_insights`
5. `generated_resources`

每项状态统一为：

- `available`
- `partial`
- `missing`

建议输出一个内部结构：

```json
{
  "goal": "diagnosis",
  "input_readiness": {
    "learner_profile": "available",
    "knowledge_states": "partial",
    "practice_records": "available",
    "collective_insights": "missing",
    "generated_resources": "available"
  },
  "degrade_mode": [],
  "route_plan": []
}
```

### 4.2 Route Decision

`Route Decision` 根据 `goal` 和 `input_readiness` 决定本轮执行路径。

MVP 阶段不做复杂 planner，直接采用规则表。

#### diagnosis

默认路径：

1. `ProfileAgent`
2. `KTAgent`
3. `CollectiveInsightAgent`
4. `DiagnosisAgent`

规则：

1. `collective_insights` 缺失时，跳过 `CollectiveInsightAgent`
2. `knowledge_states` 不完整时，`KTAgent` 走低证据模式
3. 如果 `knowledge_states` 和 `practice_records` 都缺失，`DiagnosisAgent` 只能输出 `insufficient_evidence`

#### recommendations

默认路径：

1. `ProfileAgent`
2. `DiagnosisAgent`
3. `ResourceAgent`

规则：

1. 如果没有现成 diagnosis，先补 `KTAgent -> DiagnosisAgent`
2. 如果资源生成服务不可用，`ResourceAgent` 回退为历史资源推荐
3. 如果 diagnosis 低置信度，推荐结果标记为 `exploratory`

#### learning_path

默认路径：

1. `ProfileAgent`
2. `DiagnosisAgent`
3. `PlannerAgent`

规则：

1. 如果没有 diagnosis，先补 `KTAgent -> DiagnosisAgent`
2. 如果没有 recommendations，允许 `PlannerAgent` 直接基于 diagnosis 生成最小路径
3. 如果 LLM 不可用，`PlannerAgent` 必须 fallback 到 rule planner

### 4.3 Execution

执行阶段按 `route_plan` 调用 Agent，并支持：

1. `agent_skipped`
2. `fallback_applied`

建议新增事件类型：

1. `route_decided`
2. `agent_skipped`
3. `fallback_applied`

## 5. 跳过与降级规则

MVP 允许安全降级，但不允许无证据强结论。

### 4.1 允许降级

1. 无群体洞察时，继续跑个体诊断
2. 无 profile 时，继续跑默认偏好模式
3. Planner 的 LLM 失败时，回退规则规划
4. 无资源生成服务时，改为推荐已有资源
5. KT 证据不完整时，输出低置信度 diagnosis

### 4.2 不允许降级

1. 没有证据却输出高置信度诊断
2. diagnosis 失败后继续伪造 recommendation 或 learning path
3. fallback 已发生但 trace 中没有记录原因

### 4.3 建议统一 reason code

1. `profile_missing`
2. `collective_insight_unavailable`
3. `insufficient_evidence`
4. `planner_rule_fallback`
5. `resource_generation_unavailable`

## 6. Agent 输出协议补充

当前协议建议只补 4 个最关键字段：

1. `confidence`
2. `field_status`
3. `fallback_used`
4. `fallback_reason`

示例：

```json
{
  "agent_name": "DiagnosisAgent",
  "status": "completed",
  "summary": "发现梯度下降掌握较弱",
  "result": {},
  "reason_codes": ["weak_mastery"],
  "evidences": [],
  "confidence": 0.72,
  "field_status": "inferred",
  "fallback_used": false,
  "fallback_reason": null
}
```

规则：

1. `field_status` 只使用 `confirmed`、`inferred`、`missing`
2. 没有 evidence 时，不允许高 confidence
3. fallback 结果默认不能高置信度

## 7. 反馈摘要规则

MVP 不做复杂策略学习，只做“反馈摘要进入下一轮”。

建议先统一接收四类反馈：

1. 资源反馈：点击、完成、放弃
2. 路径反馈：step 完成、step 跳过
3. 练习反馈：正确、错误、重复错误
4. 主观反馈：懂了、没懂、太快、太难

然后由一个轻量汇总器输出：

```json
{
  "recent_feedback_summary": {
    "completed_resources": 2,
    "abandoned_resources": 1,
    "struggled_knowledge_points": ["kp_gradient_descent"],
    "last_path_completion_rate": 0.4
  }
}
```

这份摘要进入下一轮 context，供以下 Agent 消费：

1. `ProfileAgent`
2. `KTAgent`
3. `ResourceAgent`
4. `PlannerAgent`

建议先定义 3 条 rerun 规则：

1. 同一知识点连续错 2 次，触发 diagnosis rerun
2. 连续放弃 2 个推荐资源，触发 recommendations rerun
3. 学习路径完成率低于 40%，触发 planner rerun

### 7.1 接口策略

这一部分尽量复用需求文档里已有接口，不额外发明新接口。

优先使用：

1. `POST /api/v1/projects/{project_id}/recommendations/{recommendation_id}/feedback`
2. `GET /api/v1/projects/{project_id}/evaluation-reports/latest`

建议做法：

1. 推荐反馈继续走现有 `recommendation feedback` 接口
2. 学习效果摘要优先复用 `evaluation-reports/latest`
3. `recent_feedback_summary` 由协同层内部 service 汇总生成，不要求先新增独立对外接口

### 7.2 仅在缺口明确时新增接口

如果现有接口无法稳定提供协同层所需摘要，MVP 只建议新增一个聚合读取接口：

`GET /api/v1/projects/{project_id}/agent-context-summary`

职责：

1. 聚合 learner profile、knowledge states、recent practice、recent feedback、latest evaluation summary
2. 只作为 `SupervisorAgent` 的上下文装配入口
3. 不替代已有明细接口

返回建议：

```json
{
  "learner_profile": {},
  "knowledge_states": [],
  "practice_records": [],
  "recent_feedback_summary": {},
  "evaluation_report_summary": {}
}
```

说明：

1. 这个接口不是必须项
2. 只有在现有 service 拼装成本过高时再新增
3. 如新增，应写清楚它是聚合只读接口，不承载写入逻辑

## 8. Harness 方案

建议只做最小版 harness，不做大平台。

目录建议：

```text
tests/agent_harness/
  fixtures/
  test_route_rules.py
  test_contracts.py
  test_fallbacks.py
  test_trace.py
```

### 8.1 测试范围

#### route rules

验证不同输入下路由是否正确。

例如：

1. 无 `collective_insights` 时是否跳过 `CollectiveInsightAgent`
2. 无 diagnosis 时是否先补 `KTAgent -> DiagnosisAgent`
3. Planner 失败时是否触发 fallback

#### contracts

验证每个 Agent 输出是否合规。

至少检查：

1. `agent_name`
2. `status`
3. `summary`
4. `confidence` 在 `0~1`
5. fallback 时是否有 `fallback_reason`

#### fallbacks

验证降级是否按规则发生。

例如：

1. diagnosis 证据不足时，不输出强结论
2. resource service 不可用时，退化为已有资源推荐
3. planner 出错时，退化为 rule planner

#### trace

验证 trace 是否完整。

至少包含：

1. `run_started`
2. `route_decided`
3. `agent_skipped`
4. `fallback_applied`
5. `run_completed` 或 `run_failed`

### 8.2 建议 fixture

建议先准备 5 个标准场景：

1. `complete_diagnosis`
2. `no_collective`
3. `insufficient_evidence`
4. `resource_fallback`
5. `planner_llm_fallback`

## 9. 开发顺序建议

建议按以下顺序推进：

1. 先改 `SupervisorAgent`
   - 增加 preflight
   - 增加 route decision
   - 增加 skip/fallback
   - 明确上下文装配来源
2. 再补输出协议
   - `confidence`
   - `field_status`
   - `fallback_used`
   - `fallback_reason`
3. 再补 feedback summary
4. 最后补 harness

## 10. 结论

这版 MVP 不需要继续增加 Agent，优先把现有协同层补成：

1. 会判断怎么跑
2. 知道什么时候降级
3. 会读取统一上下文而不是各自为政
4. 能把反馈带进下一轮
5. 改完以后能测出有没有变差

这是当前阶段最划算、也最稳定的改造方向。
