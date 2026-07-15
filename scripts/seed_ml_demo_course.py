"""Seed a compact machine-learning demo course library.

The script mirrors the DSA course seed and is idempotent for local development.
It updates existing rows by course code, chapter title, knowledge-point name,
and resource URL.
"""

# ruff: noqa: RUF001

from __future__ import annotations

import os
from dataclasses import dataclass
from uuid import uuid4

from edu_db.models import (
    Course,
    CourseChapter,
    CourseResource,
    CourseResourceKnowledgePoint,
    KnowledgePoint,
    KnowledgePointRelation,
    User,
)
from edu_db.session import get_session_factory, init_db
from sqlalchemy import or_

OWNER_ID = os.getenv("SEED_OWNER_ID", "dev-local-user")
OWNER_EMAIL = os.getenv("SEED_OWNER_EMAIL", "dev-local-user@example.com")
COURSE_CODE = "ML-DEMO"
DEFAULT_DATABASE_URL = "postgresql+psycopg2://postgres:postgres@localhost:5433/postgres"
LEGACY_RESOURCE_URLS = {
    "https://developers.google.com/machine-learning/intro-to-ml": (
        "https://developers.google.com/machine-learning/crash-course/ml-intro"
    )
}


@dataclass(frozen=True)
class ResourceSeed:
    title: str
    url: str
    resource_type: str
    description: str
    estimated_minutes: int = 15


@dataclass(frozen=True)
class KnowledgePointSeed:
    name: str
    difficulty: str
    tags: list[str]
    intro: str
    scenario: str
    framework: list[str]
    practice: str
    mistakes: list[str]


@dataclass(frozen=True)
class ChapterSeed:
    title: str
    description: str
    knowledge_points: list[KnowledgePointSeed]
    resources: list[ResourceSeed]


def markdown_body(point: KnowledgePointSeed) -> str:
    framework = "\n".join(
        f"{index}. {item}" for index, item in enumerate(point.framework, start=1)
    )
    mistakes = "\n".join(f"- {item}" for item in point.mistakes)
    return f"""## 一句话介绍
{point.intro}

## 概念与使用场景
{point.scenario}

## 核心步骤
{framework}

## 动手练习
{point.practice}

## 常见错误
{mistakes}
"""


CHAPTERS: list[ChapterSeed] = [
    ChapterSeed(
        title="机器学习入门",
        description="认识机器学习任务、标准工作流以及训练集和测试集的作用。",
        knowledge_points=[
            KnowledgePointSeed(
                name="机器学习基本概念",
                difficulty="beginner",
                tags=["machine-learning", "supervised-learning", "workflow"],
                intro="机器学习通过数据学习规律，并用学到的模型对新样本作出预测。",
                scenario="适用于分类、回归、推荐和异常检测等难以完全用固定规则描述的任务。",
                framework=[
                    "明确输入特征、预测目标与评价指标。",
                    "收集并检查具有代表性的数据。",
                    "选择模型，完成训练、验证和测试。",
                    "分析误差并迭代数据、特征或模型。",
                ],
                practice="判断房价预测、垃圾邮件识别和用户分群分别属于哪类机器学习任务。",
                mistakes=[
                    "把模型在训练数据上的表现当成真实效果。",
                    "先选择复杂算法，再倒推业务目标和评价指标。",
                ],
            ),
            KnowledgePointSeed(
                name="数据集划分与数据泄漏",
                difficulty="beginner",
                tags=["train-test-split", "validation", "data-leakage"],
                intro="训练集用于学习参数，验证集用于选择方案，测试集用于最终评估。",
                scenario="所有需要客观比较模型泛化能力的实验都应在严格隔离的数据划分上进行。",
                framework=[
                    "按任务特点选择随机、分层或时间顺序划分。",
                    "只用训练数据拟合预处理器和模型。",
                    "在验证集上调参，在测试集上只做最终确认。",
                ],
                practice="用一个二分类数据集完成 70%/15%/15% 的分层划分，并检查类别比例。",
                mistakes=[
                    "先对全量数据标准化，再划分训练集和测试集。",
                    "反复查看测试集结果并据此调整模型。",
                ],
            ),
        ],
        resources=[
            ResourceSeed(
                "Google：机器学习简介",
                "https://developers.google.com/machine-learning/intro-to-ml",
                "article",
                "用短篇内容建立监督学习、模型和数据的基本认识。",
                20,
            ),
            ResourceSeed(
                "scikit-learn：常见陷阱与推荐做法",
                "https://scikit-learn.org/stable/common_pitfalls.html",
                "article",
                "通过示例理解不一致预处理和数据泄漏问题。",
                20,
            ),
        ],
    ),
    ChapterSeed(
        title="数据准备与特征工程",
        description="把原始数据转化为可供模型稳定学习的特征。",
        knowledge_points=[
            KnowledgePointSeed(
                name="缺失值与类别特征处理",
                difficulty="beginner",
                tags=["missing-values", "categorical-features", "preprocessing"],
                intro="数据预处理用于处理缺失值、类别变量和异常格式，使输入满足模型要求。",
                scenario="表格数据通常混合数值、类别和缺失信息，需要建立可复用的处理流水线。",
                framework=[
                    "按字段类型和业务含义检查缺失模式。",
                    "对数值特征填补统计量，对类别特征增加未知值策略。",
                    "对无序类别做独热编码，对有序类别保留顺序信息。",
                    "把预处理和模型封装在同一条流水线中。",
                ],
                practice="为一个含年龄、城市和消费金额的表格设计 ColumnTransformer。",
                mistakes=[
                    "用数字编号替代无序类别，给模型制造不存在的大小关系。",
                    "线上预处理逻辑与训练阶段不一致。",
                ],
            ),
            KnowledgePointSeed(
                name="特征缩放与特征选择",
                difficulty="intermediate",
                tags=["scaling", "feature-selection", "pipeline"],
                intro="特征缩放统一数值尺度，特征选择保留对任务有效的信息。",
                scenario="距离模型、线性模型和神经网络通常受特征尺度影响，高维数据还需控制噪声。",
                framework=[
                    "判断模型是否对尺度敏感。",
                    "根据分布选择标准化、归一化或稳健缩放。",
                    "用领域知识、统计检验或模型重要性筛选特征。",
                    "把所有步骤放入交叉验证流程。",
                ],
                practice="比较逻辑回归在缩放前后的收敛速度和验证集表现。",
                mistakes=[
                    "对树模型机械地执行不必要的缩放。",
                    "在交叉验证之前使用全量数据完成特征选择。",
                ],
            ),
        ],
        resources=[
            ResourceSeed(
                "scikit-learn：组合估计器与流水线",
                "https://scikit-learn.org/stable/modules/compose.html",
                "article",
                "介绍 Pipeline 与 ColumnTransformer 的标准用法。",
                25,
            ),
            ResourceSeed(
                "scikit-learn：预处理数据",
                "https://scikit-learn.org/stable/modules/preprocessing.html",
                "article",
                "涵盖缩放、编码和常见数据变换方法。",
                20,
            ),
        ],
    ),
    ChapterSeed(
        title="经典监督学习模型",
        description="用线性模型和决策树完成回归与分类任务。",
        knowledge_points=[
            KnowledgePointSeed(
                name="线性回归与逻辑回归",
                difficulty="beginner",
                tags=["linear-regression", "logistic-regression", "baseline"],
                intro="线性回归预测连续值，逻辑回归用线性决策边界估计分类概率。",
                scenario="两者训练快速、解释性强，适合作为表格任务的基线模型。",
                framework=[
                    "构造特征矩阵和目标变量。",
                    "选择损失函数并加入适当正则化。",
                    "拟合模型并查看系数、残差或分类概率。",
                    "在独立数据上评估并检查错误样本。",
                ],
                practice="分别用线性回归预测房价、用逻辑回归预测客户是否流失。",
                mistakes=[
                    "把逻辑回归输出的概率直接当作固定阈值下的类别。",
                    "忽略强相关特征和异常值对线性模型的影响。",
                ],
            ),
            KnowledgePointSeed(
                name="决策树与随机森林",
                difficulty="intermediate",
                tags=["decision-tree", "random-forest", "ensemble"],
                intro="决策树通过特征切分建立规则，随机森林组合多棵树降低方差。",
                scenario="适合处理非线性关系和特征交互，是表格数据常用的强基线。",
                framework=[
                    "用纯度或误差下降选择切分。",
                    "限制树深、叶节点样本数等复杂度。",
                    "通过样本和特征随机化训练多棵树。",
                    "聚合多棵树的预测并分析特征重要性。",
                ],
                practice="在同一数据集上比较单棵决策树与随机森林的训练和测试分数。",
                mistakes=[
                    "不限制树深，导致训练集准确率很高但测试集效果差。",
                    "把特征重要性当作因果关系。",
                ],
            ),
        ],
        resources=[
            ResourceSeed(
                "scikit-learn：线性模型",
                "https://scikit-learn.org/stable/modules/linear_model.html",
                "article",
                "介绍常用线性回归、逻辑回归与正则化方法。",
                30,
            ),
            ResourceSeed(
                "scikit-learn：集成方法",
                "https://scikit-learn.org/stable/modules/ensemble.html",
                "article",
                "介绍随机森林等基于多模型组合的学习方法。",
                30,
            ),
        ],
    ),
    ChapterSeed(
        title="模型评估与优化",
        description="选择合适指标，使用交叉验证和参数搜索可靠地比较模型。",
        knowledge_points=[
            KnowledgePointSeed(
                name="分类与回归评价指标",
                difficulty="beginner",
                tags=["metrics", "classification", "regression"],
                intro="评价指标把模型表现转化为与任务目标一致的可比较数值。",
                scenario="类别不平衡、错误成本不同或预测连续值时，单一准确率往往不够。",
                framework=[
                    "先明确最重要的业务错误类型。",
                    "分类任务选择准确率、精确率、召回率、F1 或 AUC。",
                    "回归任务选择 MAE、RMSE 或决定系数。",
                    "结合混淆矩阵、残差图和错误样本解释指标。",
                ],
                practice="为疾病筛查和垃圾邮件过滤分别选择主要指标，并说明原因。",
                mistakes=[
                    "类别极不平衡时仍只看准确率。",
                    "在不同数据划分上直接比较两个模型的分数。",
                ],
            ),
            KnowledgePointSeed(
                name="交叉验证与超参数搜索",
                difficulty="intermediate",
                tags=["cross-validation", "hyperparameters", "model-selection"],
                intro="交叉验证用多次数据划分估计模型稳定性，参数搜索用于选择训练前设定的配置。",
                scenario="样本有限且需要比较算法、预处理方法或超参数时，交叉验证比单次划分更可靠。",
                framework=[
                    "选择与数据结构匹配的折叠策略。",
                    "定义包含预处理和模型的完整流水线。",
                    "设定候选参数空间和主要评分指标。",
                    "比较均值与波动，并在保留测试集上最终确认。",
                ],
                practice="用五折交叉验证搜索随机森林的树数量和最大深度。",
                mistakes=[
                    "忽略时间序列或同一用户样本之间的相关性。",
                    "只报告最优分数，不关注折间波动和搜索成本。",
                ],
            ),
        ],
        resources=[
            ResourceSeed(
                "scikit-learn：模型评估",
                "https://scikit-learn.org/stable/modules/model_evaluation.html",
                "article",
                "汇总分类、回归和聚类任务的评价指标。",
                25,
            ),
            ResourceSeed(
                "scikit-learn：交叉验证与参数调优",
                "https://scikit-learn.org/stable/modules/cross_validation.html",
                "article",
                "介绍数据划分、交叉验证器和模型选择流程。",
                25,
            ),
        ],
    ),
    ChapterSeed(
        title="端到端分类 Demo",
        description="把数据检查、流水线、训练和评估串成一个可复现的小项目。",
        knowledge_points=[
            KnowledgePointSeed(
                name="鸢尾花分类实验",
                difficulty="beginner",
                tags=["iris", "classification", "scikit-learn"],
                intro="鸢尾花分类用四个测量特征预测三个品种，是经典的多分类入门实验。",
                scenario="适合快速演示数据探索、模型训练、混淆矩阵和预测接口的完整流程。",
                framework=[
                    "加载数据并检查特征、标签和类别分布。",
                    "分层划分训练集与测试集。",
                    "建立标准化与逻辑回归流水线。",
                    "报告测试指标、混淆矩阵和典型错误。",
                ],
                practice="完成一个可重复运行的训练脚本，并对一条新样本输出类别与概率。",
                mistakes=[
                    "没有固定随机种子，导致每次演示结果变化。",
                    "只展示最终准确率，没有保存流程和实验配置。",
                ],
            ),
            KnowledgePointSeed(
                name="模型保存与推理",
                difficulty="intermediate",
                tags=["inference", "persistence", "deployment"],
                intro="模型保存把训练好的完整流水线持久化，推理阶段加载它并处理新输入。",
                scenario="用于把离线实验结果接入脚本、接口或演示页面。",
                framework=[
                    "保存包含预处理步骤的完整模型对象。",
                    "记录依赖版本、特征定义和训练时间。",
                    "加载模型并校验输入字段、类型和范围。",
                    "监控预测分布、延迟和真实反馈。",
                ],
                practice="保存鸢尾花分类流水线，重新加载后验证预测结果与保存前一致。",
                mistakes=[
                    "只保存分类器，遗漏训练阶段的编码或缩放步骤。",
                    "加载不可信来源的序列化模型文件。",
                ],
            ),
        ],
        resources=[
            ResourceSeed(
                "scikit-learn：鸢尾花数据集示例",
                "https://scikit-learn.org/stable/auto_examples/datasets/plot_iris_dataset.html",
                "code",
                "展示鸢尾花数据集的结构和基础可视化。",
                20,
            ),
            ResourceSeed(
                "scikit-learn：模型持久化",
                "https://scikit-learn.org/stable/model_persistence.html",
                "article",
                "说明不同模型保存方式的安全性与适用场景。",
                20,
            ),
        ],
    ),
]


RELATIONS = [
    ("机器学习基本概念", "数据集划分与数据泄漏"),
    ("数据集划分与数据泄漏", "缺失值与类别特征处理"),
    ("缺失值与类别特征处理", "特征缩放与特征选择"),
    ("特征缩放与特征选择", "线性回归与逻辑回归"),
    ("机器学习基本概念", "决策树与随机森林"),
    ("线性回归与逻辑回归", "分类与回归评价指标"),
    ("决策树与随机森林", "分类与回归评价指标"),
    ("分类与回归评价指标", "交叉验证与超参数搜索"),
    ("交叉验证与超参数搜索", "鸢尾花分类实验"),
    ("鸢尾花分类实验", "模型保存与推理"),
]


def upsert_user(db) -> User:
    user = db.query(User).filter(User.id == OWNER_ID).first()
    if user is None:
        user = User(
            id=OWNER_ID,
            username="dev-local-user",
            email=OWNER_EMAIL,
            name="Local Dev User",
        )
        db.add(user)
    else:
        user.email = user.email or OWNER_EMAIL
        user.name = user.name or "Local Dev User"
    return user


def upsert_course(db) -> Course:
    course = (
        db.query(Course)
        .filter(Course.owner_id == OWNER_ID, Course.code == COURSE_CODE)
        .first()
    )
    if course is None:
        course = Course(
            id=str(uuid4()),
            owner_id=OWNER_ID,
            code=COURSE_CODE,
            name="机器学习基础",
        )
        db.add(course)
    course.name = "机器学习基础"
    course.description = (
        "从数据准备、经典模型到评估与推理的机器学习入门 Demo，"
        "包含章节、知识点、练习建议和延伸资料。"
    )
    course.status = "active"
    return course


def upsert_chapter(
    db, course: Course, seed: ChapterSeed, position: int
) -> CourseChapter:
    chapter = (
        db.query(CourseChapter)
        .filter(CourseChapter.course_id == course.id, CourseChapter.title == seed.title)
        .first()
    )
    if chapter is None:
        chapter = CourseChapter(id=str(uuid4()), course_id=course.id, title=seed.title)
        db.add(chapter)
    chapter.description = seed.description
    chapter.position = position
    chapter.learning_objectives = [point.name for point in seed.knowledge_points]
    chapter.estimated_minutes = 45 * len(seed.knowledge_points)
    return chapter


def upsert_point(
    db,
    course: Course,
    chapter: CourseChapter,
    seed: KnowledgePointSeed,
    position: int,
) -> KnowledgePoint:
    point = (
        db.query(KnowledgePoint)
        .filter(KnowledgePoint.course_id == course.id, KnowledgePoint.name == seed.name)
        .first()
    )
    if point is None:
        point = KnowledgePoint(id=str(uuid4()), course_id=course.id, name=seed.name)
        db.add(point)
    point.chapter_id = chapter.id
    point.description = markdown_body(seed)
    point.difficulty_level = seed.difficulty
    point.position = position
    point.tags = seed.tags
    return point


def upsert_resource(
    db,
    course: Course,
    chapter: CourseChapter,
    seed: ResourceSeed,
    points: list[KnowledgePoint],
) -> CourseResource:
    candidate_urls = [seed.url]
    if legacy_url := LEGACY_RESOURCE_URLS.get(seed.url):
        candidate_urls.append(legacy_url)

    resource = (
        db.query(CourseResource)
        .filter(
            CourseResource.course_id == course.id,
            or_(
                CourseResource.source_url.in_(candidate_urls),
                CourseResource.title == seed.title,
            ),
        )
        .first()
    )
    if resource is None:
        resource = CourseResource(
            id=str(uuid4()), course_id=course.id, source_url=seed.url
        )
        db.add(resource)
    resource.chapter_id = chapter.id
    resource.source_url = seed.url
    resource.title = seed.title
    resource.description = seed.description
    resource.resource_type = seed.resource_type
    resource.source_type = "external"
    resource.difficulty_level = "beginner"
    resource.estimated_minutes = seed.estimated_minutes
    resource.license_info = "仅保存公开资料链接和自整理摘要"
    resource.target_audiences = ["beginner", "intermediate"]
    resource.extra_metadata = {"seed": "ml_demo", "chapter": chapter.title}
    db.flush()

    existing_point_ids = {
        link.knowledge_point_id for link in resource.knowledge_point_links
    }
    for point in points:
        if point.id not in existing_point_ids:
            db.add(
                CourseResourceKnowledgePoint(
                    id=str(uuid4()),
                    course_resource_id=resource.id,
                    knowledge_point_id=point.id,
                    relevance_score=1.0,
                )
            )
    return resource


def upsert_relation(
    db, course: Course, source: KnowledgePoint, target: KnowledgePoint
) -> None:
    relation = (
        db.query(KnowledgePointRelation)
        .filter(
            KnowledgePointRelation.source_knowledge_point_id == source.id,
            KnowledgePointRelation.target_knowledge_point_id == target.id,
            KnowledgePointRelation.relation_type == "prerequisite",
        )
        .first()
    )
    if relation is None:
        relation = KnowledgePointRelation(
            id=str(uuid4()),
            course_id=course.id,
            source_knowledge_point_id=source.id,
            target_knowledge_point_id=target.id,
            relation_type="prerequisite",
        )
        db.add(relation)
    relation.strength = 1.0
    relation.description = f"建议先学习「{source.name}」，再学习「{target.name}」。"


def seed() -> None:
    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    init_db(database_url)
    session_factory = get_session_factory()
    with session_factory() as db:
        upsert_user(db)
        course = upsert_course(db)
        db.flush()

        points_by_name: dict[str, KnowledgePoint] = {}
        chapter_count = 0
        point_count = 0
        resource_count = 0

        for chapter_position, chapter_seed in enumerate(CHAPTERS, start=1):
            chapter = upsert_chapter(db, course, chapter_seed, chapter_position)
            db.flush()
            chapter_count += 1

            chapter_points: list[KnowledgePoint] = []
            for point_position, point_seed in enumerate(
                chapter_seed.knowledge_points, start=1
            ):
                point = upsert_point(db, course, chapter, point_seed, point_position)
                db.flush()
                points_by_name[point.name] = point
                chapter_points.append(point)
                point_count += 1

            for resource_seed in chapter_seed.resources:
                upsert_resource(db, course, chapter, resource_seed, chapter_points)
                resource_count += 1

        for source_name, target_name in RELATIONS:
            upsert_relation(
                db, course, points_by_name[source_name], points_by_name[target_name]
            )

        db.commit()

    print(
        "Seeded machine-learning demo course: "
        f"course={COURSE_CODE}, chapters={chapter_count}, "
        f"knowledge_points={point_count}, resources={resource_count}, "
        f"relations={len(RELATIONS)}"
    )


if __name__ == "__main__":
    seed()
