import { Children, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { apiGet } from '../../api/client'

interface TrendPoint {
  date: string
  calls: number
  tokens: number
  active_users: number
  active_servers: number
}

interface Ranking {
  server_id?: string
  user_id?: string
  name?: string
  display_name?: string
  calls: number
  tokens: number
  installs?: number
}

function fmtNum(value: number | undefined): string {
  const n = Number(value || 0)
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export default function AdminAnalytics() {
  const [days, setDays] = useState(30)
  const [metric, setMetric] = useState<'calls' | 'tokens'>('calls')
  const [trend, setTrend] = useState<TrendPoint[]>([])
  const [topServers, setTopServers] = useState<Ranking[]>([])
  const [topUsers, setTopUsers] = useState<Ranking[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    Promise.all([
      apiGet<TrendPoint[]>(`/admin/analytics/daily?days=${days}`),
      apiGet<Ranking[]>(`/admin/analytics/top-servers?days=${days}&metric=${metric}`),
      apiGet<Ranking[]>(`/admin/analytics/top-users?days=${days}&metric=${metric}`),
    ])
      .then(([trendResult, serverResult, userResult]) => {
        if (cancelled) return
        setTrend(trendResult.data || [])
        setTopServers(serverResult.data || [])
        setTopUsers(userResult.data || [])
      })
      .catch(() => {
        if (!cancelled) {
          setTrend([])
          setTopServers([])
          setTopUsers([])
          setError('平台分析数据加载失败，请稍后重试')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [days, metric, reloadKey])

  const maxValue = Math.max(...trend.map(point => metric === 'tokens' ? point.tokens : point.calls), 1)
  const totalCalls = trend.reduce((sum, point) => sum + point.calls, 0)
  const totalTokens = trend.reduce((sum, point) => sum + point.tokens, 0)
  const peakUsers = Math.max(...trend.map(point => point.active_users), 0)
  const peakServers = Math.max(...trend.map(point => point.active_servers), 0)

  return (
    <div className="max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">OPERATIONS / TELEMETRY</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">📈 平台分析</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">查看所有账户的聚合 Gateway 遥测，不展示请求正文、响应正文或设备令牌。</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="flex border border-gray-300 dark:border-gray-600" role="group" aria-label="平台分析时间范围">
            {[7, 30, 90].map(value => (
              <button key={value} type="button" aria-pressed={days === value} onClick={() => setDays(value)} className={`px-3 py-2 text-xs ${days === value ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-900' : 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800'}`}>
                {value} 天
              </button>
            ))}
          </div>
          <div className="flex border border-gray-300 dark:border-gray-600" role="group" aria-label="平台分析指标">
            {(['calls', 'tokens'] as const).map(value => (
              <button key={value} type="button" aria-pressed={metric === value} onClick={() => setMetric(value)} className={`px-3 py-2 text-xs ${metric === value ? 'bg-blue-600 text-white' : 'text-gray-600 hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-800'}`}>
                {value === 'calls' ? '调用' : 'Token'}
              </button>
            ))}
          </div>
          <button type="button" onClick={() => setReloadKey(value => value + 1)} className="border border-gray-300 px-3 py-2 text-xs text-gray-600 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-800">
            刷新
          </button>
        </div>
      </header>

      {error ? (
        <div role="alert" className="py-16 text-center text-red-600">
          <p>{error}</p>
          <button type="button" onClick={() => setReloadKey(value => value + 1)} className="mt-3 text-sm text-blue-600 hover:underline">重试</button>
        </div>
      ) : loading ? (
        <div role="status" className="py-16 text-center text-sm text-gray-400">正在加载平台遥测...</div>
      ) : (
        <>
          <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Metric label="时间范围调用" value={fmtNum(totalCalls)} hint={`${days} 天内全部账号的真实工具调用`} />
            <Metric label="时间范围 Token" value={fmtNum(totalTokens)} hint="Gateway 本地估算的 Token 总量" />
            <Metric label="峰值活跃用户" value={fmtNum(peakUsers)} hint="单日产生调用的用户峰值" />
            <Metric label="峰值活跃 Server" value={fmtNum(peakServers)} hint="单日产生调用的 Server 峰值" />
          </section>

          <section className="border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
            <div className="flex items-end justify-between gap-3">
              <div>
                <h2 className="font-semibold text-gray-900 dark:text-white">每日聚合趋势</h2>
                <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">当前显示：{metric === 'calls' ? '调用次数' : '估算 Token'}。</p>
              </div>
              <span className="text-xs text-gray-400">数据口径：telemetry_events</span>
            </div>
            {trend.length > 0 ? (
              <>
                <div className="mt-5 flex h-48 items-end gap-1">
                  {trend.map(point => {
                    const value = metric === 'tokens' ? point.tokens : point.calls
                    return (
                      <div key={point.date} className="group flex h-full flex-1 items-end" title={`${point.date}: ${fmtNum(value)} ${metric === 'tokens' ? 'Token' : '调用'}`}>
                        <div className="w-full rounded-t-sm bg-blue-500 transition-opacity group-hover:opacity-70 dark:bg-blue-400" style={{ height: `${Math.max((value / maxValue) * 100, 3)}%` }} />
                      </div>
                    )
                  })}
                </div>
                <div className="mt-2 flex justify-between text-[10px] text-gray-400">
                  <span>{trend[0]?.date}</span>
                  <span>{trend[trend.length - 1]?.date}</span>
                </div>
              </>
            ) : <div className="py-12 text-center text-sm text-gray-400">暂无平台遥测数据</div>}
          </section>

          <section className="grid min-w-0 gap-4 md:grid-cols-2">
            <RankingPanel title="🏆 活跃 Server" empty="暂无 Server 活跃数据">
              {topServers.map((item, index) => (
                <div key={item.server_id} className="flex min-w-0 items-center justify-between gap-3 border-b border-gray-100 py-2.5 text-sm last:border-0 dark:border-gray-700">
                  <span className="min-w-0 flex-1 truncate text-gray-700 dark:text-gray-300" title={item.name || item.server_id}>{index + 1}. {item.name || item.server_id}</span>
                  <span className="shrink-0 text-xs text-gray-400">📞 {fmtNum(item.calls)} · 🔤 {fmtNum(item.tokens)}</span>
                </div>
              ))}
            </RankingPanel>
            <RankingPanel title="👥 活跃用户" empty="暂无用户活跃数据">
              {topUsers.map((item, index) => (
                <div key={item.user_id} className="flex min-w-0 items-center justify-between gap-3 border-b border-gray-100 py-2.5 text-sm last:border-0 dark:border-gray-700">
                  <span className="min-w-0 flex-1 truncate text-gray-700 dark:text-gray-300" title={item.display_name || item.user_id}>{index + 1}. {item.display_name || item.user_id}</span>
                  <span className="shrink-0 text-xs text-gray-400">📞 {fmtNum(item.calls)} · 🔤 {fmtNum(item.tokens)}</span>
                </div>
              ))}
            </RankingPanel>
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

function RankingPanel({ title, empty, children }: { title: string; empty: string; children: ReactNode }) {
  const hasItems = Children.count(children) > 0
  return (
    <section className="min-w-0 border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
      <h2 className="font-semibold text-gray-900 dark:text-white">{title}</h2>
      <div className="mt-2">{hasItems ? children : <p className="py-6 text-sm text-gray-400">{empty}</p>}</div>
    </section>
  )
}
