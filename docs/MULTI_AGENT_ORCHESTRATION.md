# Multi-Agent Orchestration Layer

## Overview

本文档定义“多智能体协同编排层”的第一版实现方案。该层负责把学习画像、知识状态、群体洞察、诊断、资源推荐和学习路径规划串成一条可追踪的协同链路，并对外提供诊断、推荐、学习路径和 trace 查询能力。

第一版目标是先跑通稳定的串行编排链路，再考虑异步 worker、SSE 实时推送和部分并行执行。

## Scope

### In Scope

- `SupervisorAgent` 与子 Agent 的固定串行协调机制
- Agent 间统一输入输出协议
- 三条主业务链路：
  - `POST /api/v1/projects/{project_id}/diagnosis`
  - `POST /api/v1/projects/{project_id}/recommendations/generate`
  - `POST /api/v1/projects/{project_id}/learning-paths/generate`
- Agent 协同过程 trace 记录
- 可供前端消费的事件结构，第一版至少支持 trace 查询，后续可扩展 SSE
- 基于画像、知识状态和课程资源结果生成诊断、推荐和路径规划

### Out of Scope

- 课程库表结构设计
- `learner_profiles` 的底层 CRUD
- `student_knowledge_states` 的底层 CRUD
- 知识点、课程、资源库的基础数据维护
- 前端页面细节
- 资源内容本身的生成
- `mastery_score` 等知识状态字段的底层更新规则

## Dependency Boundaries

编排层必须依赖已有业务接口或 service 能力读取事实数据，不允许绕开已有接口直接维护底层数据。

必须依赖的能力：

- `GET /api/v1/projects/{project_id}/learner-profile`
- `PATCH /api/v1/projects/{project_id}/learner-profile`
- `GET /api/v1/projects/{project_id}/knowledge-states`
- `GET /api/v1/projects/{project_id}/knowledge-states/{knowledge_point_id}`
- 课程、章节、知识点、资源相关接口或 service

Agent 约束：

- 不定义第二套 learner profile 结构
- 不直接修改 `learner_profiles` 表
- 不定义第二套 knowledge state 字段
- 不绕开既有接口或 service 做底层写库
- `ProfileAgent` 第一版建议只读画像并输出更新建议；如需真实更新，只能通过 `PATCH /learner-profile`

## Suggested Code Layout

建议把协议、编排和路由分层放置，避免把 Agent 逻辑写进 FastAPI router。

```text
src/shared/core/src/edu_core/schemas/
  agent_orchestration.py       # AgentName、RunStatus、AgentRunContext、AgentResult、AgentEvent
  diagnosis.py                 # diagnosis API 请求/响应 schema
  recommendations.py           # recommendation API 请求/响应 schema
  learning_paths.py            # learning path API 请求/响应 schema

src/shared/ai/src/edu_ai/agents/orchestration/
  supervisor.py                # SupervisorAgent
  base.py                      # BaseAgent 协议与通用 helper
  profile_agent.py
  kt_agent.py
  collective_insight_agent.py
  diagnosis_agent.py
  resource_agent.py
  planner_agent.py
  trace.py                     # trace writer / in-memory fallback

src/shared/core/src/edu_core/services/
  diagnosis.py
  recommendations.py
  learning_paths.py

src/edu-api/routers/
  diagnosis.py
  recommendations.py
  learning_paths.py
```

当前仓库已有 `study-plans` 路由。如果需求文档明确要求 `/learning-paths`，建议新增 `learning_paths.py` router；不要直接把新链路混入旧 `study-plans`，除非产品层确认两者等价。

## Protocol Layer

协议层先于业务逻辑提交。所有 Agent 必须只通过统一上下文和统一结果包通信。

### Enums

```python
from enum import StrEnum


class AgentName(StrEnum):
    SUPERVISOR = "SupervisorAgent"
    PROFILE = "ProfileAgent"
    KT = "KTAgent"
    COLLECTIVE_INSIGHT = "CollectiveInsightAgent"
    DIAGNOSIS = "DiagnosisAgent"
    RESOURCE = "ResourceAgent"
    PLANNER = "PlannerAgent"


class RunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class FieldStatus(StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    MISSING = "missing"


class Trend(StrEnum):
    UP = "up"
    DOWN = "down"
    STABLE = "stable"
```

### AgentRunContext

`AgentRunContext` 是整条链路共享上下文。

```json
{
  "run_id": "run_001",
  "project_id": "project_001",
  "student_id": "user_001",
  "goal": "diagnosis",
  "trigger": {
    "type": "practice_record",
    "id": "practice_001"
  },
  "context": {
    "learner_profile": null,
    "knowledge_states": [],
    "knowledge_state_details": {},
    "course": null,
    "chapters": [],
    "knowledge_points": [],
    "practice_records": [],
    "documents": [],
    "collective_insights": []
  },
  "artifacts": {},
  "meta": {
    "requested_at": "2026-06-15T20:00:00Z"
  }
}
```

约束：

- `context` 只放事实数据，例如接口读取到的画像、知识状态、课程、资源、练习记录
- `artifacts` 只放 Agent 的结构化产物，例如诊断结果、推荐结果、学习路径
- 不允许把自由文本长段当成唯一中间产物
- 每个 Agent 只能消费 `context` 与已有 `artifacts`，不能依赖其他 Agent 的私有变量

### AgentResult

每个 Agent 必须返回统一包络。

```json
{
  "agent_name": "DiagnosisAgent",
  "status": "completed",
  "summary": "识别到学生当前主要问题是学习率概念误解",
  "result": {},
  "reason_codes": ["weak_mastery", "collective_pattern_match"],
  "reason_text": ["相关知识点掌握度较低", "与群体常见错因模式匹配"],
  "evidences": [
    {
      "source_type": "knowledge_state",
      "source_id": "kp_gradient_descent"
    }
  ],
  "next_actions": ["generate_recommendations", "generate_learning_path"]
}
```

### AgentEvent

所有协同日志统一为 `AgentEvent`。

```json
{
  "event_type": "agent_step",
  "run_id": "run_001",
  "agent_name": "ProfileAgent",
  "status": "completed",
  "summary": "已读取学习画像并识别关键偏好字段",
  "timestamp": "2026-06-15T20:00:03Z",
  "payload": {
    "used_fields": ["preferred_resource_type", "learning_style"]
  }
}
```

最少事件类型：

- `run_started`
- `agent_step`
- `artifact_updated`
- `run_completed`
- `run_failed`

## Orchestration Layer

第一版 `SupervisorAgent` 固定串行执行。

执行顺序：

1. `ProfileAgent`
2. `KTAgent`
3. `CollectiveInsightAgent`
4. `DiagnosisAgent`
5. `ResourceAgent`
6. `PlannerAgent`
7. `SupervisorAgent` 汇总

`SupervisorAgent` 负责：

- 创建 `run_id`
- 初始化 `AgentRunContext`
- 读取必要事实数据并写入 `context`
- 按顺序调用子 Agent
- 收集 `AgentResult`
- 写入 `AgentEvent` trace
- 把 `artifacts` 汇总成接口返回值
- 在异常时写入 `run_failed` 事件，并返回可诊断错误

`SupervisorAgent` 不负责：

- 画像字段推理细节
- 知识诊断算法细节
- 推荐排序细节
- 学习路径步骤生成细节

### Supervisor Pseudocode

```python
class SupervisorAgent:
    async def run(self, request: RunRequest) -> SupervisorRunResult:
        run_id = create_run_id()
        ctx = init_context(run_id, request)
        trace.append(run_started(ctx))

        try:
            for agent in self.agents:
                result = await agent.run(ctx)
                ctx.artifacts[agent.artifact_key] = result.result
                trace.append(agent_step(ctx, result))
                trace.append(artifact_updated(ctx, agent.artifact_key, result.result))

            final_result = build_final_response(ctx)
            trace.append(run_completed(ctx, final_result))
            return final_result

        except Exception as exc:
            trace.append(run_failed(ctx, exc))
            raise
```

## Agent Layer

### ProfileAgent

职责：

- 读取学生画像
- 判断画像完整度
- 提供后续诊断和推荐需要的偏好上下文
- 生成画像更新建议，但第一版不直接写库

输入：

- `project_id`
- 当前用户 `student_id`
- `GET /learner-profile` 返回值
- 可选：最近对话摘要、练习记录

输出 artifact key：`profile`

```json
{
  "profile_snapshot": {
    "id": "profile_001",
    "status": "active",
    "profile_data": {},
    "completeness_score": 0.72
  },
  "profile_missing_fields": ["preferred_pace"],
  "profile_update_suggestions": [
    {
      "field": "preferred_resource_type",
      "value": "visual",
      "source": "recent_chat",
      "confidence": 0.76
    }
  ],
  "profile_summary": {
    "learning_style": "visual",
    "preferred_resource_type": ["mind_map", "ppt_outline"]
  }
}
```

### KTAgent

职责：

- 读取当前项目下知识状态
- 识别薄弱知识点和强项
- 为诊断提供结构化证据

输入：

- `GET /knowledge-states`
- 可选：`GET /knowledge-states/{knowledge_point_id}`
- 课程知识点列表

输出 artifact key：`knowledge_state`

```json
{
  "knowledge_state_summary": {
    "weak_points": [
      {
        "knowledge_point_id": "kp_gradient_descent",
        "mastery_score": 41,
        "trend": "down",
        "status": "struggling"
      }
    ],
    "strong_points": [],
    "overall_mastery": 58
  },
  "knowledge_state_details": {
    "kp_gradient_descent": {
      "mastery_score": 41,
      "confidence": 0.83,
      "trend": "down",
      "attempt_count": 6,
      "correct_count": 2
    }
  }
}
```

### CollectiveInsightAgent

职责：

- 匹配群体常见错因
- 提供有效补救模式
- 为诊断和推荐补充群体证据

输入：

- 当前薄弱知识点列表
- 可选：历史错因模式库

输出 artifact key：`collective_insight`

```json
{
  "matched_patterns": [
    {
      "pattern_code": "learning_rate_misconception",
      "match_score": 0.78
    }
  ],
  "effective_interventions": [
    {
      "type": "resource",
      "target_form": "dynamic_visualization",
      "evidence_level": "medium"
    }
  ]
}
```

第一版如果没有真实群体数据，可以使用 stub，但必须保持输出格式稳定。

### DiagnosisAgent

职责：

- 输出根因诊断
- 生成 `/diagnosis` 主结果

输入：

- `profile_summary`
- `knowledge_state_summary`
- `knowledge_state_details`
- `matched_patterns`
- 触发源信息

输出 artifact key：`diagnosis`

```json
{
  "diagnosis": {
    "summary": "学生当前主要问题不是公式记忆，而是对学习率作用机制的概念误解",
    "root_causes": [
      {
        "type": "misconception",
        "label": "误以为学习率越大越好",
        "confidence": 0.84
      }
    ],
    "related_knowledge_points": [
      {
        "id": "kp_gradient_descent",
        "mastery": 0.41
      }
    ],
    "collective_support": {
      "matched_pattern": "learning_rate_misconception",
      "match_score": 0.78
    },
    "explanation": [
      "最近两次相关练习连续出错",
      "掌握度持续下降",
      "与群体常见错因模式高度匹配"
    ]
  }
}
```

### ResourceAgent

职责：

- 生成推荐项
- 支撑 `/recommendations`
- 只决定“推什么、为什么推、分数是多少”

输入：

- `diagnosis`
- `profile_summary`
- `knowledge_state_summary`
- 课程资源库接口结果
- 可选：resource package 相关已有结果

输出 artifact key：`recommendations`

```json
{
  "recommendations": [
    {
      "id": "rec_001",
      "recommendation_type": "resource",
      "target_id": "resource_001",
      "title": "梯度下降动态图解",
      "reason_codes": [
        "weak_mastery",
        "recent_wrong_answers",
        "profile_preference_match"
      ],
      "reason_text": [
        "相关知识点掌握度较低",
        "近期练习连续出错",
        "符合视觉化学习偏好"
      ],
      "score": 0.89,
      "recommended_by": "ResourceAgent"
    }
  ]
}
```

### PlannerAgent

职责：

- 基于诊断和推荐生成步骤化学习路径
- 支撑 `/learning-paths`

输入：

- `diagnosis`
- `recommendations`
- `profile_summary`
- `knowledge_state_summary`

输出 artifact key：`learning_path`

```json
{
  "learning_path": {
    "title": "梯度下降补强路径",
    "estimated_minutes": 90,
    "path_steps": [
      {
        "step_no": 1,
        "type": "resource",
        "target_id": "resource_001",
        "title": "先看梯度下降动态图解",
        "reason": "先建立直观概念"
      },
      {
        "step_no": 2,
        "type": "practice",
        "target_id": "practice_set_001",
        "title": "完成学习率专项练习",
        "reason": "验证是否纠正误解"
      }
    ],
    "based_on_profile_fields": [
      "preferred_resource_type",
      "learning_style"
    ],
    "based_on_knowledge_points": [
      "kp_gradient_descent"
    ],
    "adjust_reasons": [
      "薄弱知识点优先",
      "符合视觉化偏好"
    ]
  }
}
```

## API Layer

### Diagnosis

第一版必须完成：

- `POST /api/v1/projects/{project_id}/diagnosis`
- `GET /api/v1/projects/{project_id}/diagnosis/{diagnosis_id}`
- `GET /api/v1/projects/{project_id}/diagnosis/{diagnosis_id}/trace`

`POST /diagnosis` 职责：

- 创建 run
- 调用 `SupervisorAgent`
- 持久化或缓存诊断结果
- 返回结构化 diagnosis artifact

建议响应：

```json
{
  "diagnosis_id": "diag_001",
  "run_id": "run_001",
  "project_id": "project_001",
  "student_id": "user_001",
  "status": "completed",
  "diagnosis": {},
  "next_actions": ["generate_recommendations", "generate_learning_path"],
  "created_at": "2026-06-15T20:00:00Z"
}
```

`GET /trace` 职责：

- 返回同一 `run_id` 下所有 `AgentEvent`
- 事件按 `timestamp` 升序排列

### Recommendations

第一版重点完成：

- `GET /api/v1/projects/{project_id}/recommendations`
- `POST /api/v1/projects/{project_id}/recommendations/generate`

后续补齐：

- `POST /api/v1/projects/{project_id}/recommendations/{recommendation_id}/feedback`

`POST /recommendations/generate` 应优先消费已有 diagnosis 结果。如果请求没有传 `diagnosis_id`，可触发一次完整 Supervisor 链路，但必须在响应中返回新的 `run_id`。

建议响应：

```json
{
  "run_id": "run_001",
  "project_id": "project_001",
  "recommendations": [],
  "based_on_diagnosis_id": "diag_001",
  "created_at": "2026-06-15T20:00:00Z"
}
```

### Learning Paths

第一版重点完成：

- `POST /api/v1/projects/{project_id}/learning-paths/generate`
- `GET /api/v1/projects/{project_id}/learning-paths/latest`

后续补齐：

- `GET /api/v1/projects/{project_id}/learning-paths`
- `PATCH /api/v1/projects/{project_id}/learning-paths/{path_id}`
- `POST /api/v1/projects/{project_id}/learning-paths/{path_id}/adjust`

建议响应：

```json
{
  "path_id": "path_001",
  "run_id": "run_001",
  "project_id": "project_001",
  "learning_path": {},
  "based_on_diagnosis_id": "diag_001",
  "based_on_recommendation_ids": ["rec_001"],
  "created_at": "2026-06-15T20:00:00Z"
}
```

## Trace And Event Stream

第一版必须实现 trace 查询，因为这是协同编排层的核心可见性能力。

前端最少需要展示：

- 当前处理阶段
- 哪个 Agent 已完成
- 当前产出的模块结果
- 最终汇总结果

前端可消费事件格式：

```json
{
  "event_type": "agent_step",
  "agent_name": "DiagnosisAgent",
  "status": "completed",
  "summary": "已生成根因诊断",
  "payload": {
    "related_knowledge_points": ["kp_gradient_descent"]
  }
}
```

### SSE Extension

第一版可以先只做 `GET /trace`。如果需要实时效果，再新增：

- `GET /api/v1/projects/{project_id}/runs/{run_id}/events`

SSE event body 仍然使用 `AgentEvent`，不要为 SSE 另定义一套事件协议。

## Persistence Strategy

第一版有两种可选落地方式：

1. 内存 trace store
   - 适合演示和快速开发
   - 进程重启后 trace 丢失
   - 不适合正式环境

2. 数据库存储
   - 建议表：`agent_runs`、`agent_events`、`agent_artifacts`
   - 适合 diagnosis、recommendation、learning path 后续查询
   - 更适合支持 `GET /diagnosis/{id}`、`GET /trace`、`latest`

如果时间有限，建议先用内存 store 打通接口，再把 store 抽象成接口，后续替换为数据库实现。

## Error Handling

统一失败规则：

- 单个 Agent 抛错时，`SupervisorAgent` 写入 `run_failed`
- `AgentResult.status` 可为 `failed`，但错误仍要进入 trace
- 接口层返回明确的 `run_id`，方便前端或测试人员查询失败步骤
- 下游接口不可用时，Agent 应返回结构化错误摘要，避免只有 Python exception 文本

建议失败事件：

```json
{
  "event_type": "run_failed",
  "run_id": "run_001",
  "agent_name": "KTAgent",
  "status": "failed",
  "summary": "读取知识状态失败",
  "timestamp": "2026-06-15T20:00:03Z",
  "payload": {
    "error_code": "knowledge_state_fetch_failed",
    "retryable": true
  }
}
```

## Development Order

建议按以下顺序实现：

1. 协议层
   - 新增 schema、枚举、trace event 格式
   - 为 `AgentRunContext`、`AgentResult`、`AgentEvent` 写基础单元测试

2. Supervisor 骨架
   - 子 Agent 可先返回 mock artifact
   - 先跑通完整串行链路
   - 每一步都写 trace

3. `/diagnosis`
   - 接入 `ProfileAgent`、`KTAgent`、`CollectiveInsightAgent`、`DiagnosisAgent`
   - 完成 `POST /diagnosis` 与 `GET /trace`

4. `/recommendations`
   - 消费 diagnosis 结果
   - 接入 `ResourceAgent`
   - 完成 generate 和 list

5. `/learning-paths`
   - 消费 diagnosis 和 recommendations
   - 接入 `PlannerAgent`
   - 完成 generate 和 latest

6. 增强能力
   - SSE
   - 异步 worker
   - 局部并行
   - 数据库存储 trace 和 artifact

## Acceptance Checklist

- 协议层 schema 已提交，且 Agent 不返回裸 dict 或纯文本报告
- `SupervisorAgent` 能生成唯一 `run_id`
- 固定串行链路可完整执行
- 每个 Agent 都返回 `AgentResult`
- 每个关键步骤都写入 `AgentEvent`
- `/diagnosis` 能返回结构化根因诊断
- `/diagnosis/{diagnosis_id}/trace` 能返回完整协同过程
- `/recommendations/generate` 能基于 diagnosis 生成推荐项
- `/learning-paths/generate` 能基于 diagnosis 和 recommendations 生成步骤化路径
- 编排层没有直接写 `learner_profiles` 或 `student_knowledge_states`
- 前端可以通过 trace 展示 Agent 执行阶段和最终结果
