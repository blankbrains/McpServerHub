import { useEffect, useState } from 'react'
import { apiGet } from '../../api/client'

interface ValidationData {
  participants: {
    total: number
    by_role: Record<string, number>
    targets: Record<string, number>
  }
  stages: Record<string, number>
  metrics: {
    first_call_median_minutes: number | null
    connection_state_understood: { responses: number; rate: number }
    verify_without_logs: { responses: number; rate: number }
    recovery_succeeded: { responses: number; rate: number }
  }
}

const stages = [
  ['device_created', '创建设备'],
  ['setup_started', '开始接入'],
  ['setup_completed', '完成配置'],
  ['gateway_first_seen', 'Gateway 在线'],
  ['first_tool_call', '首次工具调用'],
] as const

const roles = [
  ['individual_user', '个人 MCP 用户'],
  ['server_publisher', 'MCP Server 开发者'],
  ['team_admin', '小型团队管理员'],
] as const

export default function AdminValidation() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState<ValidationData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    apiGet<ValidationData>(`/admin/analytics/user-validation?days=${days}`)
      .then(result => {
        if (!cancelled) setData(result.data || null)
      })
      .catch(() => {
        if (!cancelled) {
          setData(null)
          setError('接入验证数据加载失败')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [days, reloadKey])

  const participants = data?.participants.total || 0

  return (
    <div className="max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">OPERATIONS / ONBOARDING</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">✅ 接入验证</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">观察用户从创建设备到首次真实调用的完成情况，不展示用户身份或本地配置。</p>
        </div>
        <div className="flex border border-gray-300 dark:border-gray-600" role="group" aria-label="接入验证时间范围">
          {[7, 30, 90].map(value => (
            <button key={value} type="button" aria-pressed={days === value} onClick={() => setDays(value)}
              className={`px-3 py-2 text-xs ${days === value ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900' : 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800'}`}>
              {value} 天
            </button>
          ))}
        </div>
      </header>

      {error ? (
        <div role="alert" className="py-16 text-center text-red-600">
          <p>{error}</p>
          <button type="button" onClick={() => setReloadKey(value => value + 1)} className="mt-3 text-sm text-blue-600 hover:underline">重试</button>
        </div>
      ) : loading ? (
        <div role="status" className="py-16 text-center text-sm text-gray-400">正在加载接入验证数据...</div>
      ) : !data ? (
        <div className="py-16 text-center text-sm text-gray-400">暂无接入验证数据</div>
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="参与者" value={String(participants)} hint="所选时间内自愿参与验证的用户" />
            <Metric label="首次调用中位时间" value={data.metrics.first_call_median_minutes === null ? '暂无' : `${data.metrics.first_call_median_minutes} 分钟`} hint="从创建设备到首次真实工具调用" />
            <Metric label="理解接入状态" value={`${data.metrics.connection_state_understood.rate}%`} hint={`${data.metrics.connection_state_understood.responses} 份有效回答`} />
            <Metric label="无需日志完成验证" value={`${data.metrics.verify_without_logs.rate}%`} hint={`${data.metrics.verify_without_logs.responses} 份有效回答`} />
          </section>

          <section className="border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
            <div>
              <h2 className="font-semibold text-gray-900 dark:text-white">接入漏斗</h2>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">每一步按参与者去重，后续阶段人数不应高于前序阶段。</p>
            </div>
            <div className="mt-5 grid gap-2 md:grid-cols-5">
              {stages.map(([id, label], index) => {
                const count = data.stages[id] || 0
                const rate = participants ? Math.round(count / participants * 100) : 0
                return (
                  <div key={id} className="relative border border-gray-200 p-4 dark:border-gray-700">
                    <p className="text-xs text-gray-400">步骤 {index + 1}</p>
                    <p className="mt-1 text-sm font-medium text-gray-800 dark:text-gray-200">{label}</p>
                    <p className="mt-3 text-2xl font-bold text-gray-900 dark:text-white">{count}</p>
                    <p className="text-xs text-gray-400">{rate}% 参与者</p>
                  </div>
                )
              })}
            </div>
          </section>

          <section className="grid gap-4 md:grid-cols-[minmax(0,1fr)_320px]">
            <div className="border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
              <h2 className="font-semibold text-gray-900 dark:text-white">参与者覆盖</h2>
              <div className="mt-4 divide-y divide-gray-100 dark:divide-gray-700">
                {roles.map(([id, label]) => (
                  <div key={id} className="flex items-center justify-between py-3 text-sm">
                    <span className="text-gray-600 dark:text-gray-300">{label}</span>
                    <span className="font-medium text-gray-900 dark:text-white">
                      {data.participants.by_role[id] || 0} / {data.participants.targets[id] || 0}
                    </span>
                  </div>
                ))}
              </div>
            </div>
            <div className="border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
              <h2 className="font-semibold text-gray-900 dark:text-white">恢复验证</h2>
              <p className="mt-4 text-3xl font-bold text-gray-900 dark:text-white">{data.metrics.recovery_succeeded.rate}%</p>
              <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">{data.metrics.recovery_succeeded.responses} 份回答确认安全断开和恢复符合预期。</p>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
      <p className="mt-1 text-sm font-medium text-gray-700 dark:text-gray-200">{label}</p>
      <p className="mt-1 text-xs leading-5 text-gray-400">{hint}</p>
    </div>
  )
}
