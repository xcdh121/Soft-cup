# EduAgent 项目需求文档（按最新流程规划更新）

## 1. 文档目标

本文档用于统一当前 EduAgent 项目的产品需求、核心业务流程、智能体分工、数据模型建议与接口建议，方便前后端、算法、数据与产品在同一语义下协同开发。

本次更新重点覆盖以下新增能力：

1. 对话式学生画像构建与持续更新
2. 多智能体协同编排
3. KT（Knowledge Tracing）知识追踪与溯源
4. 群体学习模式挖掘
5. 可解释推荐与诊断
6. 围绕“课程资料库 -> 画像 -> 学习 -> 诊断 -> 推荐 -> 路径调整”的业务闭环

## 2. 当前项目基础

结合当前仓库实现，系统已经具备以下基础能力：

1. 项目与用户体系
   - 支持用户、项目、课程资料的组织管理。
   - 支持以 `project` 为学习空间承载文档、聊天与学习资源。
2. 文档处理与资料检索
   - 支持 PDF、DOCX、PPTX、TXT 等资料上传。
   - 通过异步 worker 完成文档解析、切分、向量化与入库。
   - 已具备基于 `pgvector` 的语义检索能力。
3. 对话式学习
   - 已有基于 RAG 的聊天能力。
   - 已支持流式响应与工具调用。
4. 学习资源生成
   - 已支持笔记、测验、闪卡、思维导图、学习计划、资源包等能力。
5. 实践与学习记录
   - 已有练习记录、测验记录、学习计划与基础使用统计能力。
6. 工程基础
   - 前端：React + TypeScript
   - 后端：FastAPI
   - 异步任务：Worker + Queue
   - 数据层：PostgreSQL / Supabase / Azure Blob / pgvector

结论：当前项目已具备“单 Agent + 多工具 + RAG + 资源生成”的基础，下一阶段应升级为“面向个体学习闭环的多智能体教育系统”。

## 3. 产品目标

系统目标不再只是回答问题或生成学习材料，而是围绕一个学生的长期学习过程提供持续支持：

1. 通过对话建立和更新学生画像
2. 基于知识点粒度持续追踪掌握度
3. 结合个体行为与群体规律做薄弱点诊断
4. 给出有理由的资源推荐和学习路径调整
5. 持续输出讲解、练习、测验、图解、PPT 大纲等资源包
6. 形成“诊断 - 干预 - 反馈 - 再诊断”的闭环

## 4. 核心业务主流程

```text
课程资料库建设
  -> 学生通过对话建立画像
  -> 系统初始化知识掌握状态
  -> 学生学习、提问、练习
  -> KTAgent 更新个体知识状态
  -> CollectiveInsightAgent 提供群体常错规律
  -> DiagnosisAgent 进行错因诊断和溯源
  -> ResourceAgent 推荐个性化资源
  -> Content / Media / Assessment Agent 生成资源包
  -> PlannerAgent 调整学习路径
  -> 学生继续学习
  -> 系统持续更新画像、KT 和推荐策略
```

## 5. 功能需求

### 5.1 对话式学生画像构建

学生画像必须通过自然语言对话逐步构建，而不是只依赖表单一次性填写。画像至少包含以下 12 个维度：

1. 专业背景
2. 学历层次
3. 当前课程
4. 学习目标
5. 知识基础
6. 学习进度
7. 资源偏好
8. 认知风格
9. 易错点类型
10. 实践能力水平
11. 可用学习时间
12. 当前学习状态

补充要求：

1. 每个画像字段都应支持 `value + confidence + evidence + updated_at`。
2. 画像更新来源包括：
   - 用户主动描述
   - 历史对话抽取
   - 练习/测验结果
   - 资源点击与完成情况
   - 学生反馈
3. 系统需保留画像变更记录，便于解释“为什么画像发生变化”。
4. 若信息不足，允许字段为空，但要记录“待补充”状态。

建议字段示例：

```json
{
  "current_course": {
    "value": "机器学习基础",
    "confidence": 0.92,
    "evidence": [
      {
        "source_type": "chat_message",
        "source_id": "msg_123",
        "excerpt": "我最近在学机器学习里的逻辑回归"
      }
    ],
    "updated_at": "2026-06-05T10:00:00Z"
  }
}
```

### 5.2 多智能体协同

建议采用 Supervisor 驱动的多智能体架构。

智能体职责如下：

1. `SupervisorAgent`
   - 负责任务理解、拆解、调度、汇总输出
   - 判断本轮是否需要画像更新、KT 更新、诊断、推荐、内容生成、路径调整
2. `ProfileAgent`
   - 从对话和行为中抽取学生画像
   - 执行画像初始化、字段补全、增量更新
3. `KTAgent`
   - 维护知识点掌握度
   - 根据练习、测验、提问、资源学习行为更新掌握值
4. `CollectiveInsightAgent`
   - 从群体数据中提炼常见错因、难点模式、有效补救策略
5. `DiagnosisAgent`
   - 结合个体 KT 与群体规律判断真实薄弱原因
   - 输出根因链路和可信度
6. `ResourceAgent`
   - 检索课程资料库与历史生成资源
   - 输出候选资源与推荐理由
7. `ContentAgent`
   - 生成个性化讲解、总结、案例说明
8. `AssessmentAgent`
   - 生成练习题、测验题、错因诊断题
9. `MediaAgent`
   - 生成思维导图、PPT 大纲、流程图、动画分镜脚本等多模态资源
10. `PlannerAgent`
   - 负责生成和调整个性化学习路径

推荐的协同顺序：

```text
SupervisorAgent
  -> ProfileAgent
  -> KTAgent
  -> CollectiveInsightAgent
  -> DiagnosisAgent
  -> ResourceAgent
  -> ContentAgent / AssessmentAgent / MediaAgent
  -> PlannerAgent
  -> SupervisorAgent 汇总输出
```

### 5.3 KT 知识追踪与溯源

系统需要维护学生在知识点层面的掌握度，掌握度建议为 `0-100` 或 `0-1` 的标准化分值。

示例：

```text
导数：75%
损失函数：52%
梯度下降：41%
逻辑回归：28%
神经网络：10%
```

除掌握度外，还应支持“薄弱原因溯源”：

```text
逻辑回归掌握差
  <- 梯度下降掌握差
  <- 损失函数理解不足
  <- 导数基础一般
```

功能要求：

1. 每个知识点需记录当前掌握度、趋势、最近更新时间、证据来源。
2. 每次练习或提问后允许增量更新相关知识点状态。
3. 支持先修依赖关系，形成知识点有向图。
4. 支持输出“根因链路”而不是只输出单点薄弱结论。
5. 支持记录诊断类型，例如：
   - 概念混淆
   - 前置知识不足
   - 公式使用错误
   - 计算错误
   - 代码实现错误
   - 题意理解错误

### 5.4 群体学习模式挖掘

系统不仅看单个学生，也要从多个学生学习数据中总结共性规律。

示例：

```text
知识点：梯度下降

群体常见错因：
1. 误以为学习率越大越好：31%
2. 混淆梯度方向和下降方向：27%
3. 不理解损失函数曲面：22%
4. 代码实现中矩阵维度错误：20%
```

功能要求：

1. 支持按课程、章节、知识点、题型聚合群体行为。
2. 支持输出群体常见错因及其比例。
3. 支持输出不同补救资源的群体效果表现。
4. 在个体诊断时允许引用群体模式作为辅助证据，但不能替代个体行为本身。

个体迁移示例：

```text
当前学生在“梯度下降”题目中连续出错，
且错误选项与群体中“学习率误解型”高度相似，
因此系统判断该学生可能属于“学习率误解型”。
```

### 5.5 可解释推荐与诊断

系统每一次推荐、掌握度判断、路径调整都必须给出理由。

示例：

```text
推荐资源：梯度下降动态图解
推荐原因：
1. 你在学习率相关题目中连续答错 2 次。
2. 你的梯度下降掌握度为 41%，低于继续学习逻辑回归的建议阈值。
3. 群体数据表明，与你相似的学生通过动态图解资源提升效果最好。
4. 该资源符合你偏好的“图解 + 实操”学习方式。
```

解释信息建议包含：

1. 触发事件
2. 关联知识点
3. 当前学生状态
4. 群体依据
5. 推荐资源与画像匹配关系
6. 后续预期目标

### 5.6 个性化资源包生成

系统应在当前已有笔记、测验、闪卡、思维导图能力基础上，支持生成统一的个性化资源包。

一个资源包至少支持以下资源中的 5 类：

1. 个性化讲解文档
2. 思维导图
3. 分层练习题
4. 测验题
5. PPT 大纲
6. 案例说明
7. 代码实操任务
8. 动画/视频分镜脚本

资源包生成必须结合：

1. 学生画像
2. 当前课程与知识点
3. KT 薄弱点
4. 学习目标
5. 可用学习时间

### 5.7 学习路径动态规划

学习路径必须从“静态计划”升级为“基于画像、KT 和诊断结果的动态路径”。

每个路径步骤建议包含：

1. 学习目标
2. 关联知识点
3. 前置要求
4. 推荐资源
5. 推荐练习
6. 预计时间
7. 完成标准
8. 下一步触发条件

路径调整触发条件示例：

1. 某知识点错误率连续升高
2. 某前置知识未达阈值
3. 某补救资源完成后效果明显提升
4. 学生可用时间变化
5. 学生学习状态变化

## 6. 课程资料库建设要求

课程资料库需从“文档堆积”升级为“知识点可索引的结构化资料库”。

建议至少支持：

1. `courses`
   - 课程基础信息
2. `course_chapters`
   - 章节结构
3. `knowledge_points`
   - 知识点、难度、前置关系
4. `course_resources`
   - 原始资料、公开视频链接、示例代码、题库、案例、生成资源
5. `knowledge_point_relations`
   - 知识点依赖、包含、并列、应用关系

课程与现有项目体系的关系：

1. 一个 `course` 可以包含多个 `project`，一个 `project` 最多归属于一个 `course`。
2. `project` 继续作为具体学习空间，承载文档、聊天、测验、练习记录和生成资源。
3. 现有业务数据继续通过 `project_id` 关联项目，再通过 `projects.course_id` 间接归属于课程。
4. 为兼容尚未归类的历史项目，`projects.course_id` 允许暂时为空。

资源元数据至少包含：

1. 资源类型
2. 关联知识点
3. 难度等级
4. 预计学习时长
5. 资源来源
6. 版权/许可说明
7. 推荐适用人群

## 7. 数据模型建议

以下为建议新增或扩展的数据模型，名称尽量与当前项目风格保持一致。

### 7.1 学生画像相关

1. `learner_profiles`
   - 学生画像主表
2. `learner_profile_fields`
   - 画像字段明细，支持 `field_key/value/confidence/status`
3. `learner_profile_evidences`
   - 字段证据来源
4. `learner_profile_revisions`
   - 画像变更历史

### 7.2 知识追踪相关

1. `knowledge_points`
   - 知识点主表
2. `knowledge_point_relations`
   - 先修关系、依赖关系、关联关系
3. `student_knowledge_states`
   - 学生对知识点的掌握状态
4. `knowledge_state_events`
   - 每次更新的事件日志
5. `knowledge_diagnoses`
   - 错因诊断结果
6. `knowledge_root_causes`
   - 溯源链路节点或边

### 7.3 群体洞察相关

1. `collective_insights`
   - 群体模式分析结果
2. `collective_misconception_patterns`
   - 常见错因模式
3. `collective_resource_effectiveness`
   - 资源干预效果统计

### 7.4 学习规划与推荐相关

1. `learning_paths`
   - 个性化学习路径
2. `learning_path_steps`
   - 路径步骤
3. `recommendations`
   - 推荐记录
4. `recommendation_reasons`
   - 推荐理由明细
5. `assessment_reports`
   - 学习效果报告

### 7.5 智能体过程留痕

1. `agent_runs`
   - 一次协同运行的主记录
2. `agent_run_steps`
   - 各 Agent 执行明细
3. `agent_decisions`
   - 关键判断与理由

建议：

1. 对外展示不直接暴露完整推理链，只保留“可解释摘要”。
2. 内部保留 agent trace，便于调试、回放和评估。

## 8. 接口设计建议

接口命名建议尽量延续当前风格：`/api/v1/projects/{project_id}/...`。

### 8.1 学生画像接口

```text
GET    /api/v1/projects/{project_id}/learner-profile
PUT    /api/v1/projects/{project_id}/learner-profile
PATCH  /api/v1/projects/{project_id}/learner-profile
GET    /api/v1/projects/{project_id}/learner-profile/revisions
POST   /api/v1/projects/{project_id}/learner-profile/refresh
```

职责建议：

1. `GET /learner-profile`
   - 获取当前项目下用户最新画像
2. `PUT /learner-profile`
   - 首次初始化画像，适合 onboarding 或问卷导入
3. `PATCH /learner-profile`
   - 手动修改局部字段
4. `GET /learner-profile/revisions`
   - 获取画像变化历史
5. `POST /learner-profile/refresh`
   - 触发基于最新对话/练习记录的自动更新

建议响应结构：

```json
{
  "id": "profile_001",
  "project_id": "project_001",
  "user_id": "user_001",
  "fields": {
    "major_background": {
      "value": "计算机科学",
      "confidence": 0.95,
      "status": "confirmed",
      "evidence_count": 2,
      "updated_at": "2026-06-05T10:00:00Z"
    },
    "current_learning_state": {
      "value": "焦虑但愿意投入",
      "confidence": 0.71,
      "status": "inferred",
      "evidence_count": 1,
      "updated_at": "2026-06-05T10:10:00Z"
    }
  },
  "missing_fields": ["available_study_time", "resource_preference"],
  "updated_at": "2026-06-05T10:10:00Z"
}
```

### 8.2 KT 知识追踪接口

```text
GET    /api/v1/projects/{project_id}/knowledge-states
GET    /api/v1/projects/{project_id}/knowledge-states/{knowledge_point_id}
POST   /api/v1/projects/{project_id}/knowledge-states/refresh
GET    /api/v1/projects/{project_id}/knowledge-graph
GET    /api/v1/projects/{project_id}/knowledge-diagnoses
GET    /api/v1/projects/{project_id}/knowledge-diagnoses/{diagnosis_id}
```

职责建议：

1. `GET /knowledge-states`
   - 返回当前学生知识点掌握列表，支持章节、课程、薄弱状态筛选
2. `GET /knowledge-states/{knowledge_point_id}`
   - 返回单知识点状态、趋势、证据、根因链路
3. `POST /knowledge-states/refresh`
   - 根据最新学习事件刷新 KT
4. `GET /knowledge-graph`
   - 返回知识图谱结构，供前端可视化
5. `GET /knowledge-diagnoses`
   - 返回近期诊断记录

单知识点返回建议：

```json
{
  "knowledge_point_id": "kp_logistic_regression",
  "knowledge_point_name": "逻辑回归",
  "mastery": 0.28,
  "trend": "down",
  "last_event_at": "2026-06-05T10:20:00Z",
  "evidences": [
    {
      "event_type": "quiz_attempt",
      "source_id": "attempt_001",
      "impact": -0.12
    }
  ],
  "root_causes": [
    {
      "knowledge_point_id": "kp_gradient_descent",
      "name": "梯度下降",
      "mastery": 0.41,
      "confidence": 0.88
    },
    {
      "knowledge_point_id": "kp_loss_function",
      "name": "损失函数",
      "mastery": 0.52,
      "confidence": 0.73
    }
  ]
}
```

### 8.3 群体洞察接口

```text
GET    /api/v1/projects/{project_id}/collective-insights
GET    /api/v1/projects/{project_id}/collective-insights/{knowledge_point_id}
POST   /api/v1/projects/{project_id}/collective-insights/rebuild
```

职责建议：

1. `GET /collective-insights`
   - 支持按课程、章节、知识点查看群体模式
2. `GET /collective-insights/{knowledge_point_id}`
   - 获取单知识点常见错因、群体补救策略效果
3. `POST /collective-insights/rebuild`
   - 触发重算，适合定时任务或运营后台使用

### 8.4 诊断接口

```text
POST   /api/v1/projects/{project_id}/diagnosis
GET    /api/v1/projects/{project_id}/diagnosis/{diagnosis_id}
GET    /api/v1/projects/{project_id}/diagnosis/{diagnosis_id}/trace
```

诊断接口建议输入：

```json
{
  "trigger_type": "practice_record",
  "trigger_id": "practice_001",
  "knowledge_point_ids": ["kp_gradient_descent"],
  "include_collective_insight": true
}
```

诊断接口建议输出：

```json
{
  "id": "diag_001",
  "summary": "学生当前主要问题不是公式记忆，而是对学习率作用的概念误解。",
  "root_causes": [
    {
      "type": "misconception",
      "label": "学习率越大越好",
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
    "最近两次练习均在学习率题目上出错",
    "错误选项模式与群体“学习率误解型”高度接近",
    "该问题已阻塞后续逻辑回归学习"
  ]
}
```

### 8.5 推荐接口

```text
GET    /api/v1/projects/{project_id}/recommendations
POST   /api/v1/projects/{project_id}/recommendations/generate
POST   /api/v1/projects/{project_id}/recommendations/{recommendation_id}/feedback
```

建议：

1. 推荐接口直接返回“推荐项 + 理由 + 来源依据”
2. 推荐项支持资源、练习、路径步骤、复习动作四类
3. 推荐反馈用于后续优化排序策略

推荐结果示例：

```json
{
  "id": "rec_001",
  "recommendation_type": "resource",
  "target_id": "resource_001",
  "title": "梯度下降动态图解",
  "reason_codes": [
    "weak_mastery",
    "recent_wrong_answers",
    "collective_effective_resource",
    "profile_preference_match"
  ],
  "reason_text": [
    "你在学习率相关题目中连续答错 2 次",
    "你的梯度下降掌握度为 41%",
    "相似学生使用动态图解资源的提升效果更好",
    "该资源匹配你的图解 + 实操偏好"
  ],
  "score": 0.89
}
```

### 8.6 资源包接口

当前项目已经具备以下接口：

```text
GET    /api/v1/projects/{project_id}/resource-packages
POST   /api/v1/projects/{project_id}/resource-packages/generate
GET    /api/v1/projects/{project_id}/resource-packages/{package_id}
GET    /api/v1/projects/{project_id}/resource-packages/{package_id}/stream
DELETE /api/v1/projects/{project_id}/resource-packages/{package_id}

GET    /api/v1/projects/{project_id}/resource-packages/{package_id}/resources
GET    /api/v1/projects/{project_id}/generated-resources/{resource_id}
PATCH  /api/v1/projects/{project_id}/generated-resources/{resource_id}
POST   /api/v1/projects/{project_id}/generated-resources/{resource_id}/regenerate
```

建议本次仅扩展入参，不改变主路径，避免前端和已有服务大改。

`POST /resource-packages/generate` 建议扩展字段：

```json
{
  "profile_id": "profile_001",
  "target_topic": "梯度下降",
  "target_goal": "补齐逻辑回归前置基础",
  "source_document_ids": ["doc_001", "doc_002"],
  "knowledge_point_ids": ["kp_gradient_descent", "kp_loss_function"],
  "resource_types": [
    "lecture_note",
    "mind_map",
    "practice_set",
    "quiz",
    "ppt_outline"
  ],
  "difficulty_level": "beginner",
  "estimated_minutes": 60,
  "custom_instructions": "优先图解和代码示例",
  "diagnosis_id": "diag_001",
  "explanation_mode": "detailed"
}
```

建议响应增加：

1. `trigger_reason`
2. `recommended_by`
3. `agent_trace_summary`
4. `based_on_profile_fields`
5. `based_on_knowledge_points`

### 8.7 学习路径接口

当前项目已有：

```text
GET    /api/v1/projects/{project_id}/study-plans/latest
GET    /api/v1/projects/{project_id}/study-plans
POST   /api/v1/projects/{project_id}/study-plans/generate
```

建议分两阶段演进：

第一阶段：保留 `study-plans`，扩展内容结构；
第二阶段：新增 `learning-paths`，用于承载动态路径。

推荐新增接口：

```text
GET    /api/v1/projects/{project_id}/learning-paths/latest
GET    /api/v1/projects/{project_id}/learning-paths
POST   /api/v1/projects/{project_id}/learning-paths/generate
PATCH  /api/v1/projects/{project_id}/learning-paths/{path_id}
POST   /api/v1/projects/{project_id}/learning-paths/{path_id}/adjust
```

### 8.8 对话接口增强建议

当前聊天流接口：

```text
POST /api/v1/projects/{project_id}/chats/{chat_id}/messages/stream
```

建议在流式事件中补充以下能力：

1. `agent_status`
   - 当前由哪个 Agent 在处理
2. `profile_update_preview`
   - 本轮对话可能更新哪些画像字段
3. `knowledge_state_update_preview`
   - 本轮对话可能影响哪些知识点
4. `recommendation_preview`
   - 本轮生成的推荐摘要

建议 SSE 事件类型增加：

```json
{
  "event_type": "agent_step",
  "agent_name": "ProfileAgent",
  "status": "completed",
  "summary": "识别到用户当前课程为机器学习基础"
}
```

## 9. 前后端同步建议

### 9.1 统一枚举定义

前后端需统一以下枚举：

1. 画像字段 key
2. 画像字段状态：`confirmed / inferred / missing`
3. 掌握趋势：`up / down / stable`
4. 错因类型
5. 资源类型
6. 推荐类型
7. Agent 名称
8. 学习状态类型

建议将这些枚举沉淀到共享 schema 或前端常量文件中，避免字符串漂移。

### 9.2 统一解释结构

所有需要“可解释”的对象尽量复用统一结构：

```json
{
  "reason_codes": ["weak_mastery", "profile_match"],
  "reason_text": ["当前掌握度偏低", "匹配你的资源偏好"],
  "evidences": [
    {
      "source_type": "practice_record",
      "source_id": "practice_001"
    }
  ]
}
```

这样前端可以统一渲染“推荐原因”“诊断原因”“路径调整原因”。

### 9.3 统一异步任务状态

资源包生成、画像刷新、KT 刷新、群体洞察重算都建议使用统一状态：

```text
pending
running
completed
failed
```

必要时扩展：

```text
queued
partial_success
canceled
```

### 9.4 页面建议

前端后续建议重点补充以下页面或模块：

1. 学生画像卡片/画像详情页
2. 知识掌握热力图或知识图谱页
3. 诊断详情页
4. 推荐理由弹层
5. 学习路径时间轴
6. 多智能体协作过程面板

## 10. 分阶段实施建议

### 阶段一：最小可落地闭环

1. 建立 `learner_profile`
2. 建立 `student_knowledge_states`
3. 在聊天和练习后触发画像/KT 更新
4. 输出基础诊断和推荐理由
5. 让资源包生成接口接入画像和 KT

### 阶段二：增强诊断能力

1. 引入知识图谱和先修关系
2. 实现 KT 溯源链路
3. 上线群体错因统计
4. 支持更稳定的路径调整

### 阶段三：多智能体显式化

1. 建立 `SupervisorAgent + 子 Agent` 协调机制
2. 对外展示 Agent 协作摘要
3. 建立 agent run trace 与评估体系

## 11. 本次接口改造优先级建议

若希望尽快让前后端同步推进，推荐优先做下面 6 个接口：

1. `GET /api/v1/projects/{project_id}/learner-profile`
2. `PATCH /api/v1/projects/{project_id}/learner-profile`
3. `GET /api/v1/projects/{project_id}/knowledge-states`
4. `GET /api/v1/projects/{project_id}/knowledge-states/{knowledge_point_id}`
5. `POST /api/v1/projects/{project_id}/diagnosis`
6. 扩展 `POST /api/v1/projects/{project_id}/resource-packages/generate`

原因：

1. 这 6 个接口即可支撑画像、KT、诊断、推荐生成的最小闭环。
2. 兼容当前项目已有 chat、study-plan、resource-package 结构。
3. 前端可先做画像卡片、知识状态面板、诊断抽屉、推荐理由卡片。

## 12. 验收标准建议

建议验收不只看“能不能生成内容”，还要看“是否形成个体化闭环”。

核心验收点：

1. 能通过对话生成学生画像，且至少包含 12 个维度
2. 学生练习后能更新至少一个知识点掌握状态
3. 系统能给出至少一条带理由的诊断
4. 系统能给出至少一条带理由的资源推荐
5. 系统能生成至少 5 类个性化学习资源
6. 系统能根据学习结果调整一次学习路径
7. 前端可展示至少一段多智能体协作摘要

## 13. 总结

本次更新后的系统定位应明确为：

“基于课程资料库、动态学生画像、知识追踪、群体洞察和多智能体协同的个性化学习支持系统”。

相比当前版本，后续开发重点不再是单次生成某类学习材料，而是围绕学生长期学习过程，建立可更新、可诊断、可推荐、可解释、可调整的闭环机制。
## 14. 学习效果评估页补充需求（2026-06-07）

### 14.1 页面目标

新增项目级页面：

`/dashboard/p/{project_id}/learning-evaluation`

页面第一阶段先落地“练习测试 + 自动评分 + 效果展示”的前端原型，支持：

1. 学生进入项目后开始练习测试
2. 前端完成单题作答、提交、即时评分
3. 页面展示总分、正确率、分维度条形图
4. 页面展示题目解析与学习建议

第一阶段允许题目数据由前端静态配置，不阻塞页面交互开发。

### 14.2 后端接口建议补充

为让学习效果评估页从“前端原型”升级为“真实业务页面”，建议后端补充以下接口：

```text
GET    /api/v1/projects/{project_id}/practice-tests
POST   /api/v1/projects/{project_id}/practice-tests/generate
GET    /api/v1/projects/{project_id}/practice-tests/{test_id}
POST   /api/v1/projects/{project_id}/practice-tests/{test_id}/submit
GET    /api/v1/projects/{project_id}/evaluation-reports/latest
GET    /api/v1/projects/{project_id}/evaluation-reports
GET    /api/v1/projects/{project_id}/evaluation-reports/{report_id}
```

### 14.3 接口职责建议

1. `GET /practice-tests`
   - 获取当前项目下已有的练习测试列表
   - 支持按知识点、难度、创建时间筛选
2. `POST /practice-tests/generate`
   - 基于项目文档、知识点、资源包内容生成一套测试题
   - 支持指定题量、题型、目标主题、难度等级
3. `GET /practice-tests/{test_id}`
   - 获取单套测试题详情
   - 返回题干、选项、知识点、维度标签、参考答案说明
4. `POST /practice-tests/{test_id}/submit`
   - 提交学生答案
   - 返回总分、分维度得分、题目判定、解析和建议
   - 同时建议内部联动写入 `practice_records`
5. `GET /evaluation-reports/latest`
   - 获取当前项目最近一次学习效果评估结果
6. `GET /evaluation-reports`
   - 获取评估历史记录
7. `GET /evaluation-reports/{report_id}`
   - 获取单次评估报告详情，包括总体结果、维度结果、知识点结果、建议

### 14.4 建议的测试生成入参

```json
{
  "target_topic": "梯度下降",
  "knowledge_point_ids": ["kp_gradient_descent", "kp_learning_rate"],
  "difficulty_level": "intermediate",
  "question_count": 8,
  "question_types": ["single_choice"],
  "dimensions": ["知识理解", "迁移应用", "分析判断", "表达组织"]
}
```

### 14.5 建议的提交结果出参

```json
{
  "test_id": "test_001",
  "score": 78,
  "correct_count": 6,
  "total_count": 8,
  "dimension_scores": [
    {
      "dimension": "知识理解",
      "score": 100
    },
    {
      "dimension": "迁移应用",
      "score": 50
    }
  ],
  "knowledge_point_scores": [
    {
      "knowledge_point_id": "kp_gradient_descent",
      "score": 62
    }
  ],
  "question_results": [
    {
      "question_id": "q1",
      "is_correct": true,
      "explanation": "学习率过大可能导致震荡。"
    }
  ],
  "suggestions": [
    "建议补充梯度下降中的学习率案例练习",
    "建议先看知识图谱再做迁移应用题"
  ]
}
```

### 14.6 数据模型建议补充

建议新增或扩展：

1. `practice_tests`
   - 练习测试主表
2. `practice_test_questions`
   - 测试题明细
3. `practice_test_submissions`
   - 学生提交记录
4. `evaluation_reports`
   - 学习效果评估报告
5. `evaluation_dimension_scores`
   - 各维度得分明细

### 14.7 与现有能力的关系

学习效果评估页建议与现有能力做以下联动：

1. 与 `practice_records` 联动
   - 测试提交后自动写入练习记录
2. 与 `knowledge-states` 联动
   - 评估结果可作为 KT 刷新证据
3. 与 `resource-packages` 联动
   - 根据薄弱维度推荐讲解文档、思维导图、分层练习题
4. 与 `learner-profile` 联动
   - 评估结果可作为学生画像中的“学习状态 / 易错点 / 表达能力”证据
