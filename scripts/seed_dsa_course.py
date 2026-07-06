"""Seed the data-structures-and-algorithms MVP course library.

The script is idempotent for local development: it updates existing rows by
course code, chapter title, knowledge-point name, and resource URL/title.
"""

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


OWNER_ID = os.getenv("SEED_OWNER_ID", "dev-local-user")
OWNER_EMAIL = os.getenv("SEED_OWNER_EMAIL", "dev-local-user@example.com")
COURSE_CODE = "DSA-MVP"
DEFAULT_DATABASE_URL = (
    "postgresql+psycopg2://postgres:postgres@localhost:5433/postgres"
)


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
    complexity: str
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

## 核心框架
{framework}

## 复杂度
{point.complexity}

## 常见错误
{mistakes}
"""


CHAPTERS: list[ChapterSeed] = [
    ChapterSeed(
        title="复杂度与算法基础",
        description="建立算法分析、递归和基础设计思维。",
        knowledge_points=[
            KnowledgePointSeed(
                name="时间与空间复杂度",
                difficulty="beginner",
                tags=["complexity", "big-o", "analysis"],
                intro="复杂度用于衡量算法随输入规模增长时的时间和空间消耗。",
                scenario="用于比较算法优劣、估算瓶颈，并在竞赛或工程中选择合适方案。",
                framework=[
                    "确定输入规模 n 的含义。",
                    "找出循环、递归或数据结构操作的主导项。",
                    "忽略常数和低阶项，写成 Big-O 形式。",
                    "同时评估额外空间和原地修改情况。",
                ],
                complexity="复杂度本身是分析工具，常见表达包括 O(1)、O(log n)、O(n)、O(n log n)、O(n^2)。",
                mistakes=[
                    "把常数优化误认为复杂度降低。",
                    "只看时间复杂度，忽略辅助数组、递归栈等空间开销。",
                ],
            ),
            KnowledgePointSeed(
                name="递归基础",
                difficulty="beginner",
                tags=["recursion", "base-case", "call-stack"],
                intro="递归是函数通过调用自身来分解问题的编程方法。",
                scenario="适用于树、分治、回溯、动态规划等天然具有子问题结构的场景。",
                framework=[
                    "定义函数语义，明确参数代表的子问题。",
                    "写出递归终止条件。",
                    "将当前问题拆成更小的同类问题。",
                    "合并子问题结果并返回。",
                ],
                complexity="递归复杂度通常用递归树或主定理分析，空间复杂度还要考虑调用栈深度。",
                mistakes=[
                    "缺少终止条件导致无限递归。",
                    "没有明确函数语义，导致参数和返回值混乱。",
                ],
            ),
        ],
        resources=[
            ResourceSeed(
                "OI Wiki：复杂度",
                "https://oi-wiki.org/basic/complexity/",
                "article",
                "介绍时间复杂度、空间复杂度和常见分析方法。",
            ),
            ResourceSeed(
                "MIT 6.006：Introduction to Algorithms",
                "https://ocw.mit.edu/courses/6-006-introduction-to-algorithms-spring-2020/",
                "video",
                "MIT 算法导论公开课，适合作为系统学习入口。",
                45,
            ),
        ],
    ),
    ChapterSeed(
        title="线性数据结构",
        description="掌握数组、链表、栈、队列和哈希表的基本操作。",
        knowledge_points=[
            KnowledgePointSeed(
                "数组与链表",
                "beginner",
                ["array", "linked-list", "linear-structure"],
                "数组和链表是最基础的线性存储结构。",
                "数组适合随机访问，链表适合频繁插入删除，两者常用于构建更复杂结构。",
                ["比较连续存储和链式存储。", "分析访问、插入、删除操作。", "根据操作频率选择结构。"],
                "数组随机访问 O(1)，中间插入删除 O(n)；链表访问 O(n)，已知节点插入删除 O(1)。",
                ["忽略数组扩容成本。", "链表操作时丢失 next 指针。"],
            ),
            KnowledgePointSeed(
                "栈与队列",
                "beginner",
                ["stack", "queue", "monotonic-queue"],
                "栈和队列分别表示后进先出和先进先出的受限线性结构。",
                "常用于括号匹配、表达式计算、BFS、单调结构和任务调度。",
                ["明确入栈/出栈或入队/出队规则。", "维护容器状态。", "在合适时机处理队首或栈顶元素。"],
                "基础操作通常为 O(1)，空间复杂度 O(n)。",
                ["混淆栈和队列的弹出顺序。", "循环队列中边界条件处理错误。"],
            ),
            KnowledgePointSeed(
                "哈希表",
                "beginner",
                ["hash-table", "map", "set"],
                "哈希表通过哈希函数将键映射到存储位置以支持快速查询。",
                "适合去重、计数、两数之和、缓存和快速存在性判断。",
                ["设计键和值。", "选择 map 或 set。", "处理插入、查询和更新。", "关注冲突和键的不可变性。"],
                "平均查询、插入、删除 O(1)，最坏情况可退化到 O(n)，空间复杂度 O(n)。",
                ["把可变对象作为键。", "忘记处理重复键的计数或覆盖逻辑。"],
            ),
        ],
        resources=[
            ResourceSeed("OI Wiki：数据结构", "https://oi-wiki.org/ds/", "article", "系统梳理常见数据结构。"),
            ResourceSeed("VisuAlgo：数据结构可视化", "https://visualgo.net/en", "visualization", "用动画理解数据结构操作。"),
            ResourceSeed("The Algorithms：Python 数据结构", "https://github.com/TheAlgorithms/Python/tree/master/data_structures", "code", "Python 数据结构代码实现集合。"),
        ],
    ),
    ChapterSeed(
        title="字符串",
        description="学习字符串处理、哈希、模式匹配和字典树。",
        knowledge_points=[
            KnowledgePointSeed("字符串基础与哈希", "intermediate", ["string", "hash", "rolling-hash"], "字符串哈希将字符串映射为数值以便快速比较。", "常用于子串判等、去重和模式匹配预处理。", ["选择哈希基数和模数。", "预处理前缀哈希。", "用区间公式计算子串哈希。"], "预处理 O(n)，单次子串哈希 O(1)，空间 O(n)。", ["忽略哈希冲突。", "下标和幂次对齐错误。"]),
            KnowledgePointSeed("KMP 字符串匹配", "advanced", ["kmp", "pattern-matching", "prefix-function"], "KMP 利用前缀函数避免模式串匹配时重复回退。", "适合在线性时间内查找模式串在文本中的出现位置。", ["构建 next 或 prefix 数组。", "扫描文本并维护当前匹配长度。", "失配时按前缀信息回退。"], "构建 O(m)，匹配 O(n)，空间 O(m)。", ["next 数组定义混乱。", "失配回退后忘记继续比较当前字符。"]),
            KnowledgePointSeed("Trie 字典树", "intermediate", ["trie", "prefix-tree", "string"], "Trie 是按字符路径组织字符串集合的树形结构。", "常用于前缀查询、自动补全、词频统计和异或字典树。", ["从根节点逐字符插入。", "不存在的边创建新节点。", "在终止节点记录单词状态或计数。"], "插入和查询 O(L)，L 为字符串长度，空间与节点总数相关。", ["没有标记单词结束。", "删除节点时误删共享前缀。"]),
        ],
        resources=[
            ResourceSeed("OI Wiki：字符串", "https://oi-wiki.org/string/", "article", "字符串算法专题资料。"),
            ResourceSeed("cp-algorithms：字符串哈希", "https://cp-algorithms.com/string/string-hashing.html", "article", "字符串哈希公式和实现细节。"),
            ResourceSeed("The Algorithms：Python 字符串算法", "https://github.com/TheAlgorithms/Python/tree/master/strings", "code", "Python 字符串算法实现集合。"),
        ],
    ),
    ChapterSeed(
        title="树",
        description="理解树结构及其遍历、搜索和优先队列应用。",
        knowledge_points=[
            KnowledgePointSeed("二叉树与遍历", "beginner", ["binary-tree", "traversal", "dfs"], "二叉树是每个节点最多有两个孩子的树结构。", "适用于层级数据表达、递归训练和许多树形算法。", ["定义节点结构。", "选择前序、中序、后序或层序遍历。", "递归或迭代访问节点。"], "遍历时间 O(n)，递归空间 O(h)，h 为树高。", ["递归终止条件遗漏空节点。", "混淆前中后序的访问时机。"]),
            KnowledgePointSeed("二叉搜索树", "intermediate", ["bst", "binary-search-tree"], "二叉搜索树通过左小右大的性质支持有序查询。", "适合动态维护有序集合、范围查询和理解平衡树基础。", ["按大小关系查找位置。", "插入新节点。", "删除时处理叶子、单子树和双子树三种情况。"], "平均操作 O(log n)，退化时 O(n)，空间 O(h)。", ["删除双子节点时没有正确替换后继或前驱。", "忽略树退化问题。"]),
            KnowledgePointSeed("堆与优先队列", "intermediate", ["heap", "priority-queue"], "堆是一种维护最值快速访问的完全二叉树结构。", "常用于 TopK、调度、Dijkstra 和合并有序数据。", ["选择大根堆或小根堆。", "插入后上浮。", "删除堆顶后下沉。"], "插入和删除 O(log n)，访问堆顶 O(1)，建堆 O(n)。", ["把堆误认为全局有序。", "比较函数方向写反。"]),
        ],
        resources=[
            ResourceSeed("VisuAlgo：二叉搜索树", "https://visualgo.net/en/bst", "visualization", "二叉搜索树操作可视化。"),
            ResourceSeed("VisuAlgo：堆", "https://visualgo.net/en/heap", "visualization", "堆和优先队列操作可视化。"),
            ResourceSeed("Open Data Structures：Binary Trees", "https://opendatastructures.org/ods-python/6_Binary_Trees.html", "article", "二叉树结构与操作讲解。"),
        ],
    ),
    ChapterSeed(
        title="图",
        description="掌握图的存储、遍历和最短路径基础。",
        knowledge_points=[
            KnowledgePointSeed("图的概念与存储", "beginner", ["graph", "adjacency-list", "adjacency-matrix"], "图由顶点和边组成，用来表达对象之间的关系。", "适合建模网络、路径、依赖关系和状态转移。", ["确定有向/无向和带权/无权。", "选择邻接表或邻接矩阵。", "按输入构建图结构。"], "邻接表空间 O(V+E)，邻接矩阵空间 O(V^2)。", ["没有区分有向边和无向边。", "节点编号映射不一致。"]),
            KnowledgePointSeed("DFS 与 BFS", "beginner", ["dfs", "bfs", "graph-traversal"], "DFS 深入探索分支，BFS 按层扩展节点。", "DFS 常用于连通性和回溯，BFS 常用于无权最短路径和层序搜索。", ["建立 visited 标记。", "选择栈/递归或队列。", "按邻接节点扩展。", "记录层数、父节点或路径信息。"], "时间 O(V+E)，空间 O(V)。", ["访问标记太晚导致重复入队。", "忘记记录距离或层数。"]),
            KnowledgePointSeed("最短路径", "advanced", ["shortest-path", "dijkstra", "bellman-ford"], "最短路径算法用于寻找图中两个或多个节点之间的最小代价路径。", "适用于路由、地图、依赖代价和状态图优化。", ["判断边权是否非负。", "无权图用 BFS。", "非负权图用 Dijkstra。", "存在负权时考虑 Bellman-Ford。"], "BFS O(V+E)，Dijkstra 使用堆为 O((V+E)log V)。", ["对负权边错误使用 Dijkstra。", "松弛条件和优先队列过期状态处理错误。"]),
        ],
        resources=[
            ResourceSeed("OI Wiki：图论", "https://oi-wiki.org/graph/", "article", "图论基础和常见算法资料。"),
            ResourceSeed("VisuAlgo：DFS/BFS 可视化", "https://visualgo.net/en/dfsbfs", "visualization", "通过动画演示 DFS 和 BFS 执行过程。"),
            ResourceSeed("cp-algorithms：图算法", "https://cp-algorithms.com/graph/", "article", "图算法专题和实现说明。"),
        ],
    ),
    ChapterSeed(
        title="查找与排序",
        description="掌握二分查找、归并排序和快速排序。",
        knowledge_points=[
            KnowledgePointSeed("二分查找", "beginner", ["binary-search", "search"], "二分查找在有序空间中每次排除一半候选答案。", "适合有序数组查找、边界定位和答案二分。", ["确定单调性。", "定义左右边界和循环条件。", "根据 mid 判断收缩区间。", "返回目标或边界位置。"], "时间 O(log n)，空间 O(1)。", ["边界更新导致死循环。", "没有明确查找第一个还是最后一个满足条件的位置。"]),
            KnowledgePointSeed("归并排序", "intermediate", ["merge-sort", "divide-and-conquer", "sorting"], "归并排序通过分治拆分数组并合并有序子数组。", "适合稳定排序、链表排序和逆序对统计。", ["递归拆分区间。", "分别排序左右部分。", "双指针合并有序结果。"], "时间 O(n log n)，空间 O(n)。", ["合并时漏掉剩余元素。", "区间边界使用不统一。"]),
            KnowledgePointSeed("快速排序", "intermediate", ["quick-sort", "partition", "sorting"], "快速排序通过分区让基准左侧小、右侧大，再递归处理。", "适合平均效率高的通用排序，也可扩展到快速选择。", ["选择 pivot。", "执行 partition。", "递归处理左右区间。"], "平均 O(n log n)，最坏 O(n^2)，空间平均 O(log n)。", ["pivot 选择导致退化。", "分区循环边界处理错误。"]),
        ],
        resources=[
            ResourceSeed("VisuAlgo：排序可视化", "https://visualgo.net/en/sorting", "visualization", "排序算法动画演示。"),
            ResourceSeed("OI Wiki：排序", "https://oi-wiki.org/basic/sort-intro/", "article", "排序算法基础介绍。"),
            ResourceSeed("The Algorithms：Python 排序算法", "https://github.com/TheAlgorithms/Python/tree/master/sorts", "code", "Python 排序算法实现集合。"),
        ],
    ),
    ChapterSeed(
        title="分治与回溯",
        description="学习递归设计、问题拆分和搜索剪枝。",
        knowledge_points=[
            KnowledgePointSeed("递归与分治设计", "intermediate", ["divide-and-conquer", "recursion"], "分治将问题拆成若干子问题，分别解决后合并答案。", "适用于排序、区间统计、最近点对和大规模问题拆分。", ["定义子问题。", "递归求解子问题。", "设计合并逻辑。", "分析递归规模和层数。"], "常见形式 T(n)=aT(n/b)+f(n)，可用递归树或主定理分析。", ["子问题没有缩小。", "合并阶段遗漏跨区间情况。"]),
            KnowledgePointSeed("回溯与剪枝", "intermediate", ["backtracking", "pruning", "search"], "回溯通过试探、撤销和剪枝搜索解空间。", "常用于排列组合、棋盘问题、约束满足和路径枚举。", ["定义状态和选择列表。", "做选择并进入下一层。", "达到终止条件时记录答案。", "撤销选择并尝试其他分支。"], "复杂度通常与搜索树规模相关，剪枝可显著减少实际搜索量。", ["忘记撤销状态。", "剪枝条件过强导致漏解。"]),
        ],
        resources=[
            ResourceSeed("OI Wiki：递归与分治", "https://oi-wiki.org/basic/divide-and-conquer/", "article", "递归与分治思想资料。"),
            ResourceSeed("The Algorithms：Python 回溯算法", "https://github.com/TheAlgorithms/Python/tree/master/backtracking", "code", "Python 回溯算法实现集合。"),
            ResourceSeed("LeetCode：Backtracking 题目", "https://leetcode.com/tag/backtracking/", "problem", "回溯专题题目入口。", 30),
        ],
    ),
    ChapterSeed(
        title="动态规划与贪心",
        description="掌握状态设计、转移方程和局部最优策略。",
        knowledge_points=[
            KnowledgePointSeed("动态规划基础", "intermediate", ["dynamic-programming", "state-transition"], "动态规划通过保存子问题结果避免重复计算。", "适合最优子结构和重叠子问题明显的计数、最值和可行性问题。", ["定义状态。", "写出状态转移。", "确定初始化和遍历顺序。", "返回目标状态。"], "通常为状态数量乘以转移代价，空间可根据依赖关系优化。", ["状态定义不完整。", "遍历顺序和依赖方向冲突。"]),
            KnowledgePointSeed("背包问题", "advanced", ["knapsack", "dynamic-programming"], "背包问题是在容量约束下选择物品以优化价值的经典 DP 模型。", "常用于资源分配、组合选择和约束优化问题。", ["确定 0/1、完全或多重背包类型。", "定义容量维度状态。", "按类型选择正序或逆序遍历。"], "0/1 背包常见时间 O(nC)，空间可优化到 O(C)。", ["0/1 背包容量循环方向写反。", "初始化不可达状态处理错误。"]),
            KnowledgePointSeed("贪心算法", "intermediate", ["greedy", "optimization"], "贪心算法每一步选择当前看起来最优的决策。", "适用于区间调度、哈夫曼编码、最小生成树等可证明局部最优推出全局最优的问题。", ["寻找候选贪心策略。", "排序或维护优先队列。", "证明交换性质或最优子结构。", "按策略逐步构造答案。"], "复杂度常由排序 O(n log n) 或堆操作决定。", ["只凭直觉使用贪心但没有证明。", "局部最优选择不满足全局最优条件。"]),
        ],
        resources=[
            ResourceSeed("OI Wiki：动态规划", "https://oi-wiki.org/dp/", "article", "动态规划基础与专题资料。"),
            ResourceSeed("OI Wiki：贪心", "https://oi-wiki.org/basic/greedy/", "article", "贪心算法思想和例题。"),
            ResourceSeed("cp-algorithms：动态规划入门", "https://cp-algorithms.com/dynamic_programming/intro-to-dp.html", "article", "动态规划入门说明。"),
        ],
    ),
]


RELATIONS = [
    ("时间与空间复杂度", "递归基础"),
    ("递归基础", "递归与分治设计"),
    ("递归与分治设计", "回溯与剪枝"),
    ("递归与分治设计", "动态规划基础"),
    ("数组与链表", "栈与队列"),
    ("数组与链表", "哈希表"),
    ("字符串基础与哈希", "KMP 字符串匹配"),
    ("字符串基础与哈希", "Trie 字典树"),
    ("二叉树与遍历", "二叉搜索树"),
    ("二叉树与遍历", "堆与优先队列"),
    ("图的概念与存储", "DFS 与 BFS"),
    ("DFS 与 BFS", "最短路径"),
    ("二分查找", "归并排序"),
    ("归并排序", "快速排序"),
    ("动态规划基础", "背包问题"),
    ("时间与空间复杂度", "贪心算法"),
]


def upsert_user(db) -> User:
    user = db.query(User).filter(User.id == OWNER_ID).first()
    if user is None:
        user = User(id=OWNER_ID, email=OWNER_EMAIL, name="Local Dev User")
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
            name="数据结构与算法知识库 MVP",
        )
        db.add(course)
    course.description = "面向网页完整浏览链路的算法课程资料库：课程、章节、知识点、正文和资源链接。"
    course.status = "active"
    return course


def upsert_chapter(db, course: Course, seed: ChapterSeed, position: int) -> CourseChapter:
    chapter = (
        db.query(CourseChapter)
        .filter(CourseChapter.course_id == course.id, CourseChapter.title == seed.title)
        .first()
    )
    if chapter is None:
        chapter = CourseChapter(
            id=str(uuid4()),
            course_id=course.id,
            title=seed.title,
        )
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
        point = KnowledgePoint(
            id=str(uuid4()),
            course_id=course.id,
            name=seed.name,
        )
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
    resource = (
        db.query(CourseResource)
        .filter(
            CourseResource.course_id == course.id,
            CourseResource.source_url == seed.url,
        )
        .first()
    )
    if resource is None:
        resource = CourseResource(
            id=str(uuid4()),
            course_id=course.id,
            source_url=seed.url,
        )
        db.add(resource)
    resource.chapter_id = chapter.id
    resource.title = seed.title
    resource.description = seed.description
    resource.resource_type = seed.resource_type
    resource.source_type = "external"
    resource.difficulty_level = "beginner"
    resource.estimated_minutes = seed.estimated_minutes
    resource.license_info = "仅保存链接和自整理摘要"
    resource.target_audiences = ["beginner", "intermediate"]
    resource.extra_metadata = {"seed": "dsa_mvp", "chapter": chapter.title}
    db.flush()

    existing = {
        link.knowledge_point_id: link
        for link in resource.knowledge_point_links
    }
    for point in points:
        if point.id not in existing:
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
    db,
    course: Course,
    source: KnowledgePoint,
    target: KnowledgePoint,
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
                point = upsert_point(
                    db, course, chapter, point_seed, point_position
                )
                db.flush()
                points_by_name[point.name] = point
                chapter_points.append(point)
                point_count += 1

            for resource_seed in chapter_seed.resources:
                upsert_resource(db, course, chapter, resource_seed, chapter_points)
                resource_count += 1

        for source_name, target_name in RELATIONS:
            upsert_relation(db, course, points_by_name[source_name], points_by_name[target_name])

        db.commit()

    print(
        "Seeded DSA course library: "
        f"course={COURSE_CODE}, chapters={chapter_count}, "
        f"knowledge_points={point_count}, resources={resource_count}, "
        f"relations={len(RELATIONS)}"
    )


if __name__ == "__main__":
    seed()
