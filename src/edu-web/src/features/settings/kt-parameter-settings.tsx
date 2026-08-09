import { Result, useAtomSet, useAtomValue } from '@effect-atom/atom-react'
import {
  BrainCircuit,
  CheckCircle2,
  Loader2,
  Plus,
  Sliders,
} from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Textarea } from '@/components/ui/textarea'
import {
  activateKTParameterSetAtom,
  createKTParameterSetAtom,
  ktParameterSetsAtom,
  setKnowledgePointKTOverrideAtom,
} from '@/data-acess/learning-closed-loop'

const defaultForm = {
  name: '专家参数 BKT',
  version: 'bkt-v1.0',
  scopeType: 'global',
  scopeId: '',
  initialMastery: '0.20',
  learnProbability: '0.12',
  slipProbability: '0.10',
  guessProbability: '0.20',
  forgetProbabilityDaily: '0.005',
  expertReason: '基于教学专家初始建议设置，未使用离线训练。',
}

const percentage = (value: number) => `${(value * 100).toFixed(1)}%`

export const KTParameterSettings = () => {
  const result = useAtomValue(ktParameterSetsAtom)
  const createParameterSet = useAtomSet(createKTParameterSetAtom, {
    mode: 'promise',
  })
  const activateParameterSet = useAtomSet(activateKTParameterSetAtom, {
    mode: 'promise',
  })
  const setKnowledgePointOverride = useAtomSet(
    setKnowledgePointKTOverrideAtom,
    { mode: 'promise' },
  )
  const [form, setForm] = useState(defaultForm)
  const [isSaving, setIsSaving] = useState(false)
  const [override, setOverride] = useState({
    knowledgePointId: '',
    parameterSetId: '',
    learnProbability: '',
    slipProbability: '',
    guessProbability: '',
    forgetProbabilityDaily: '',
    expertReason: '',
  })

  const parameterSets = Result.isSuccess(result) ? result.value : []

  const create = async () => {
    setIsSaving(true)
    try {
      await createParameterSet({
        name: form.name.trim(),
        version: form.version.trim(),
        scopeType: form.scopeType,
        scopeId: form.scopeId.trim() || undefined,
        initialMastery: Number(form.initialMastery),
        learnProbability: Number(form.learnProbability),
        slipProbability: Number(form.slipProbability),
        guessProbability: Number(form.guessProbability),
        forgetProbabilityDaily: Number(form.forgetProbabilityDaily),
        expertReason: form.expertReason.trim() || undefined,
      })
      toast.success('BKT 参数集已保存为草稿。')
    } catch {
      toast.error('BKT 参数集保存失败，请检查参数范围和版本号。')
    } finally {
      setIsSaving(false)
    }
  }

  const submitOverride = async () => {
    setIsSaving(true)
    const optionalNumber = (value: string) =>
      value.trim() ? Number(value) : undefined
    try {
      await setKnowledgePointOverride({
        knowledgePointId: override.knowledgePointId.trim(),
        parameterSetId: override.parameterSetId,
        learnProbability: optionalNumber(override.learnProbability),
        slipProbability: optionalNumber(override.slipProbability),
        guessProbability: optionalNumber(override.guessProbability),
        forgetProbabilityDaily: optionalNumber(override.forgetProbabilityDaily),
        expertReason: override.expertReason.trim() || undefined,
      })
      toast.success('知识点参数覆盖已保存。')
    } catch {
      toast.error('知识点参数覆盖保存失败。')
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <Card
      className="gap-0 py-0 shadow-none"
      data-testid="kt-parameter-settings"
    >
      <CardHeader className="gap-1 border-b px-5 py-5 sm:px-6">
        <div className="flex items-center gap-2">
          <BrainCircuit className="size-4 text-muted-foreground" />
          <CardTitle>专家参数 BKT</CardTitle>
        </div>
        <CardDescription>
          管理全局、课程参数集和知识点覆盖。所有版本都会保留，激活新版本不会删除历史事件。
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-7 p-5 sm:p-6">
        {Result.isInitial(result) || Result.isWaiting(result) ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" /> 正在加载参数集…
          </div>
        ) : Result.isFailure(result) ? (
          <div className="text-sm text-destructive">
            参数集加载失败，请确认当前账户具有管理员权限。
          </div>
        ) : (
          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>名称 / 版本</TableHead>
                  <TableHead>范围</TableHead>
                  <TableHead>P(L0)</TableHead>
                  <TableHead>P(T)</TableHead>
                  <TableHead>P(S)</TableHead>
                  <TableHead>P(G)</TableHead>
                  <TableHead>日遗忘</TableHead>
                  <TableHead className="text-right">状态</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {parameterSets.map((parameterSet) => (
                  <TableRow key={parameterSet.id}>
                    <TableCell>
                      <div className="font-medium">{parameterSet.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {parameterSet.version}
                      </div>
                    </TableCell>
                    <TableCell>
                      {parameterSet.scope_type}
                      {parameterSet.scope_id
                        ? ` · ${parameterSet.scope_id}`
                        : ''}
                    </TableCell>
                    <TableCell>
                      {percentage(parameterSet.initial_mastery)}
                    </TableCell>
                    <TableCell>
                      {percentage(parameterSet.learn_probability)}
                    </TableCell>
                    <TableCell>
                      {percentage(parameterSet.slip_probability)}
                    </TableCell>
                    <TableCell>
                      {percentage(parameterSet.guess_probability)}
                    </TableCell>
                    <TableCell>
                      {percentage(parameterSet.forget_probability_daily)}
                    </TableCell>
                    <TableCell className="text-right">
                      {parameterSet.status === 'active' ? (
                        <Badge>
                          <CheckCircle2 className="size-3" /> 已激活
                        </Badge>
                      ) : (
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={isSaving}
                          onClick={async () => {
                            setIsSaving(true)
                            try {
                              await activateParameterSet(parameterSet.id)
                              toast.success(`已激活 ${parameterSet.version}。`)
                            } catch {
                              toast.error('参数集激活失败。')
                            } finally {
                              setIsSaving(false)
                            }
                          }}
                        >
                          激活
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <section className="space-y-4" aria-label="新建 BKT 参数集">
          <div>
            <h3 className="flex items-center gap-2 font-semibold">
              <Plus className="size-4" /> 新建参数集
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              参数范围均为 0～1；新建后先保存为草稿，再由管理员明确激活。
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="kt-name">名称</Label>
              <Input
                id="kt-name"
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    name: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="kt-version">版本</Label>
              <Input
                id="kt-version"
                value={form.version}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    version: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>参数范围</Label>
              <Select
                value={form.scopeType}
                onValueChange={(value) =>
                  setForm((current) => ({ ...current, scopeType: value }))
                }
              >
                <SelectTrigger aria-label="BKT 参数范围">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="global">全局</SelectItem>
                  <SelectItem value="course">课程</SelectItem>
                  <SelectItem value="knowledge_point">知识点</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {form.scopeType !== 'global' && (
              <div className="space-y-2">
                <Label htmlFor="kt-scope-id">范围 ID</Label>
                <Input
                  id="kt-scope-id"
                  value={form.scopeId}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      scopeId: event.target.value,
                    }))
                  }
                />
              </div>
            )}
            {(
              [
                ['initialMastery', '初始掌握 P(L0)'],
                ['learnProbability', '学习转移 P(T)'],
                ['slipProbability', '失误概率 P(S)'],
                ['guessProbability', '猜测概率 P(G)'],
                ['forgetProbabilityDaily', '每日遗忘 P(F)'],
              ] as const
            ).map(([key, label]) => (
              <div key={key} className="space-y-2">
                <Label htmlFor={`kt-${key}`}>{label}</Label>
                <Input
                  id={`kt-${key}`}
                  type="number"
                  min="0"
                  max="1"
                  step="0.001"
                  value={form[key]}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }))
                  }
                />
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <Label htmlFor="kt-reason">专家设置理由</Label>
            <Textarea
              id="kt-reason"
              value={form.expertReason}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  expertReason: event.target.value,
                }))
              }
            />
          </div>
          <Button
            type="button"
            onClick={() => void create()}
            disabled={isSaving || !form.name.trim() || !form.version.trim()}
          >
            {isSaving ? <Loader2 className="size-4 animate-spin" /> : <Plus />}
            保存参数草稿
          </Button>
        </section>

        <section
          className="space-y-4 border-t pt-6"
          aria-label="知识点参数覆盖"
        >
          <div>
            <h3 className="flex items-center gap-2 font-semibold">
              <Sliders className="size-4" /> 知识点参数覆盖
            </h3>
            <p className="mt-1 text-xs text-muted-foreground">
              覆盖优先级高于课程和全局参数；留空的参数继续继承所选参数集。
            </p>
          </div>
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor="kt-knowledge-point">知识点 ID</Label>
              <Input
                id="kt-knowledge-point"
                value={override.knowledgePointId}
                onChange={(event) =>
                  setOverride((current) => ({
                    ...current,
                    knowledgePointId: event.target.value,
                  }))
                }
              />
            </div>
            <div className="space-y-2">
              <Label>基础参数集</Label>
              <Select
                value={override.parameterSetId}
                onValueChange={(value) =>
                  setOverride((current) => ({
                    ...current,
                    parameterSetId: value,
                  }))
                }
              >
                <SelectTrigger aria-label="知识点基础参数集">
                  <SelectValue placeholder="选择参数集" />
                </SelectTrigger>
                <SelectContent>
                  {parameterSets.map((parameterSet) => (
                    <SelectItem key={parameterSet.id} value={parameterSet.id}>
                      {parameterSet.name} · {parameterSet.version}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {(
              [
                ['learnProbability', '学习转移覆盖'],
                ['slipProbability', '失误概率覆盖'],
                ['guessProbability', '猜测概率覆盖'],
                ['forgetProbabilityDaily', '每日遗忘覆盖'],
              ] as const
            ).map(([key, label]) => (
              <div key={key} className="space-y-2">
                <Label htmlFor={`kt-override-${key}`}>{label}</Label>
                <Input
                  id={`kt-override-${key}`}
                  type="number"
                  min="0"
                  max="1"
                  step="0.001"
                  value={override[key]}
                  placeholder="继承基础参数"
                  onChange={(event) =>
                    setOverride((current) => ({
                      ...current,
                      [key]: event.target.value,
                    }))
                  }
                />
              </div>
            ))}
          </div>
          <div className="space-y-2">
            <Label htmlFor="kt-override-reason">覆盖理由</Label>
            <Textarea
              id="kt-override-reason"
              value={override.expertReason}
              onChange={(event) =>
                setOverride((current) => ({
                  ...current,
                  expertReason: event.target.value,
                }))
              }
            />
          </div>
          <Button
            type="button"
            variant="outline"
            onClick={() => void submitOverride()}
            disabled={
              isSaving ||
              !override.knowledgePointId.trim() ||
              !override.parameterSetId
            }
          >
            保存知识点覆盖
          </Button>
        </section>
      </CardContent>
    </Card>
  )
}
