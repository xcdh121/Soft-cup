import { Badge } from '@/components/ui/badge'
import { ProjectHeader } from '@/features/project/components/project-header'
import { MindMapView } from '@/features/mind-map/components/mind-map-view'

const knowledgeGraphData = {
  nodes: [
    {
      id: 'root',
      position: { x: 0, y: 0 },
      data: { label: '机器学习基础', content: '项目核心知识域' },
    },
    {
      id: 'algorithms',
      position: { x: 180, y: 80 },
      data: { label: '核心算法' },
    },
    {
      id: 'data',
      position: { x: 180, y: 200 },
      data: { label: '数据处理' },
    },
    {
      id: 'evaluation',
      position: { x: 180, y: 320 },
      data: { label: '模型评估' },
    },
    {
      id: 'linear-regression',
      position: { x: 360, y: 40 },
      data: { label: '线性回归' },
    },
    {
      id: 'gradient-descent',
      position: { x: 360, y: 120 },
      data: { label: '梯度下降' },
    },
    {
      id: 'feature-engineering',
      position: { x: 360, y: 200 },
      data: { label: '特征工程' },
    },
    {
      id: 'normalization',
      position: { x: 360, y: 280 },
      data: { label: '归一化' },
    },
    {
      id: 'loss-function',
      position: { x: 360, y: 360 },
      data: { label: '损失函数' },
    },
    {
      id: 'overfitting',
      position: { x: 360, y: 440 },
      data: { label: '过拟合' },
    },
  ],
  edges: [
    { id: 'e1', source: 'root', target: 'algorithms' },
    { id: 'e2', source: 'root', target: 'data' },
    { id: 'e3', source: 'root', target: 'evaluation' },
    { id: 'e4', source: 'algorithms', target: 'linear-regression' },
    { id: 'e5', source: 'algorithms', target: 'gradient-descent' },
    { id: 'e6', source: 'data', target: 'feature-engineering' },
    { id: 'e7', source: 'data', target: 'normalization' },
    { id: 'e8', source: 'evaluation', target: 'loss-function' },
    { id: 'e9', source: 'evaluation', target: 'overfitting' },
  ],
}

const graphHighlights = [
  '图谱根节点用于概览当前项目的核心知识域',
  '二级节点表示模块划分，三级节点表示关键知识点',
  '后续可以接入 RAG 结果，把关系和来源文档自动补齐',
]

export const KnowledgeGraphPage = ({ projectId }: { projectId: string }) => {
  return (
    <div className="flex h-full flex-col max-h-screen">
      <ProjectHeader projectId={projectId} />

      <div className="flex flex-1 flex-col min-h-0 overflow-y-auto">
        <div className="container mx-auto flex max-w-7xl flex-1 flex-col gap-6 px-4 py-6">
          <section className="rounded-[28px] border bg-gradient-to-br from-emerald-50 via-white to-sky-50 p-6 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="space-y-3">
                <div>
                  <h1 className="text-2xl font-semibold tracking-tight">
                    知识图谱
                  </h1>
                  <p className="mt-1 text-sm text-muted-foreground">
                    用结构化关系展示当前项目中的主题、子主题与关键知识点。
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    项目级知识关系
                  </Badge>
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    支持后续自动生成
                  </Badge>
                  <Badge variant="secondary" className="rounded-full px-3 py-1">
                    可扩展到资源包推荐
                  </Badge>
                </div>
              </div>

              <div className="rounded-2xl border bg-white/80 px-4 py-3 text-sm text-muted-foreground">
                当前状态
                <div className="mt-1 text-lg font-semibold text-foreground">
                  图谱展示页已就绪
                </div>
              </div>
            </div>
          </section>

          <section className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
            <div className="min-h-[640px] rounded-[24px] border bg-background shadow-sm">
              <div className="border-b px-6 py-4">
                <h2 className="text-lg font-semibold">图谱结构</h2>
                <p className="mt-1 text-sm text-muted-foreground">
                  当前先展示静态知识结构，后续可替换为自动生成结果。
                </p>
              </div>
              <div className="h-[560px]">
                <MindMapView mapData={knowledgeGraphData} />
              </div>
            </div>

            <div className="space-y-6">
              <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                <h2 className="text-lg font-semibold">图谱说明</h2>
                <div className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                  {graphHighlights.map((item) => (
                    <p key={item}>{item}</p>
                  ))}
                </div>
              </section>

              <section className="rounded-[24px] border bg-background p-6 shadow-sm">
                <h2 className="text-lg font-semibold">建议接入方式</h2>
                <div className="mt-4 space-y-3 text-sm leading-6 text-muted-foreground">
                  <p>
                    以你当前仓库现状，我更建议先走本地 RAG + 现有
                    `TopicGraphAgent`，把图谱生成留在你们自己的链路里。
                  </p>
                  <p>
                    这样可以直接复用项目文档、索引结果和已有 AI agent，不会把前端展示绑定到外部云厂商。
                  </p>
                  <p>
                    如果后面你们更看重稳定商用能力、统一模型治理或企业级合规，再评估接华为云 API 会更合适。
                  </p>
                </div>
              </section>
            </div>
          </section>
        </div>
      </div>
    </div>
  )
}
