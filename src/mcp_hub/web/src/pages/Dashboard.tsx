import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ApiRequestError,
  ServerInfo,
  apiGet,
  getAuthState,
  getTopRated,
  getTrending,
  healthCheck,
} from '../api/client'
import InfoTooltip from '../components/InfoTooltip'
import ServerCard from '../components/ServerCard'
import StatusBadge from '../components/StatusBadge'

interface MonitorServer {
  server_id: string
  name: string
  status: string
  running: boolean
  enabled: boolean
  call_count_7d: number
  token_consumption: number
  reliability_score: number
}

interface MonitorData {
  summary: {
    total_servers: number
    running: number
    stopped: number
    offline: number
    total_calls_7d: number
    total_token_consumption: number
    avg_reliability: number
  }
  servers: MonitorServer[]
}

interface TelemetrySummary {
  active_devices: number
  active_servers: number
  total_calls: number
  total_tokens: number
  success_rate: number
  p95_duration_ms: number
  current_queue_depth: number
  last_seen_at: string | null
}

function fmtNum(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function formatLastSeen(value: string | null | undefined): string {
  if (!value) return '尚未收到数据'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '时间未知' : date.toLocaleString()
}

export default function Dashboard() {
  const authenticated = Boolean(getAuthState().token)
  const [monitor, setMonitor] = useState<MonitorData | null>(null)
  const [telemetry, setTelemetry] = useState<TelemetrySummary | null>(null)
  const [trending, setTrending] = useState<ServerInfo[]>([])
  const [topRated, setTopRated] = useState<ServerInfo[]>([])
  const [version, setVersion] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const load = async (refresh = false) => {
    if (refresh) setRefreshing(true)
    setError('')
    try {
      const [healthResult, trendingResult, topRatedResult] = await Promise.all([
        healthCheck(),
        getTrending(),
        getTopRated(),
      ])
      setVersion(healthResult.version || healthResult.data?.version || '')
      setTrending(trendingResult.slice(0, 3))
      setTopRated(topRatedResult.slice(0, 3))

      if (authenticated) {
        const [monitorResult, telemetryResult] = await Promise.all([
          apiGet<MonitorData>('/monitor/dashboard'),
          apiGet<TelemetrySummary>('/telemetry/summary?days=7'),
        ])
        setMonitor(monitorResult.data)
        setTelemetry(telemetryResult.data)
      } else {
        setMonitor(null)
        setTelemetry(null)
      }
    } catch (loadError) {
      setError(
        loadError instanceof ApiRequestError && loadError.status === 401
          ? '登录状态已失效，请重新登录。'
          : '仪表盘数据加载失败，请稍后重试。'
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void load()
  }, [authenticated])

  if (loading) {
    return <div className="py-16 text-center text-sm text-gray-500">正在加载仪表盘...</div>
  }

  const summary = monitor?.summary
  const recentServers = (monitor?.servers || []).slice(0, 6)

  return (
    <div className="mx-auto max-w-6xl space-y-7">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">仪表盘</h1>
          <p className="mt-1 text-sm text-gray-500">
            {authenticated
              ? `最近一次设备上报：${formatLastSeen(telemetry?.last_seen_at)}`
              : '登录后查看你的本地 MCP Server 运行和调用数据。'}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {version && <span className="text-xs text-gray-400">Hub {version}</span>}
          <button
            type="button"
            onClick={() => void load(true)}
            disabled={refreshing}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {refreshing ? '刷新中...' : '刷新'}
          </button>
        </div>
      </header>

      {error && <div role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {authenticated ? (
        <>
          <section aria-label="MCP 运行概览" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat
              label="追踪 Server"
              value={fmtNum(summary?.total_servers || 0)}
              description="当前账号保存的 Server 数量。"
              to="/my-servers"
            />
            <Stat
              label="当前运行"
              value={fmtNum(summary?.running || 0)}
              description="最近 3 分钟在线设备报告为运行中的 Server。"
              to="/my-servers"
              tone="green"
            />
            <Stat
              label="7 天调用"
              value={fmtNum(telemetry?.total_calls || 0)}
              description="本地 Gateway 在过去 7 天真实上报的工具调用次数。"
              to="/monitor"
              tone="blue"
            />
            <Stat
              label="7 天 Token"
              value={fmtNum(telemetry?.total_tokens || 0)}
              description="根据 MCP 请求和响应载荷估算，不等同于模型供应商账单。"
              to="/monitor"
              tone="amber"
            />
          </section>

          <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_280px]">
            <div>
              <div className="mb-3 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900">本地 Server 状态</h2>
                <Link to="/my-servers" className="text-sm text-blue-700 hover:underline">查看全部</Link>
              </div>
              {recentServers.length > 0 ? (
                <div className="divide-y divide-gray-100 border border-gray-200 bg-white">
                  {recentServers.map(server => (
                    <div key={server.server_id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <StatusBadge status={server.status} />
                      <div className="min-w-0 flex-1">
                        <Link to={`/servers/${encodeURIComponent(server.server_id)}`} className="truncate text-sm font-medium text-gray-900 hover:text-blue-700">
                          {server.name}
                        </Link>
                        <p className="truncate text-xs text-gray-500">{server.server_id}</p>
                      </div>
                      <div className="flex gap-4 text-xs text-gray-500">
                        <InfoTooltip description="过去 7 天当前用户设备上报的工具调用。">
                          <span>{fmtNum(server.call_count_7d)} 次</span>
                        </InfoTooltip>
                        <InfoTooltip description="根据 MCP 调用载荷估算的 Token。">
                          <span>{fmtNum(server.token_consumption)} Token</span>
                        </InfoTooltip>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  title="尚无本地状态"
                  description="先从市场添加 Server，再在监控页创建设备并运行一键接入命令。"
                  to="/market"
                  action="浏览市场"
                />
              )}
            </div>

            <aside className="space-y-3">
              <h2 className="text-lg font-semibold text-gray-900">连接状态</h2>
              <div className="border border-gray-200 bg-white p-4 text-sm">
                <MetricRow label="在线设备" value={telemetry?.active_devices || 0} />
                <MetricRow label="活跃 Server" value={telemetry?.active_servers || 0} />
                <MetricRow label="成功率" value={`${telemetry?.success_rate || 0}%`} />
                <MetricRow label="P95 延迟" value={`${telemetry?.p95_duration_ms || 0} ms`} />
                <MetricRow label="待传队列" value={telemetry?.current_queue_depth || 0} />
              </div>
              <Link to="/monitor" className="block rounded-md bg-gray-900 px-3 py-2 text-center text-sm font-medium text-white hover:bg-gray-800">
                打开监控详情
              </Link>
            </aside>
          </section>
        </>
      ) : (
        <EmptyState
          title="登录后启用个人监控"
          description="每个用户的数据按账号和设备令牌隔离，浏览器不会扫描你的电脑。"
          to="/guide"
          action="查看接入指南"
        />
      )}

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">热门 Server</h2>
          <Link to="/market" className="text-sm text-blue-700 hover:underline">进入市场</Link>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {trending.map(server => <ServerCard key={server.id} server={server} />)}
        </div>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">高评分 Server</h2>
          <Link to="/market?sort=rating" className="text-sm text-blue-700 hover:underline">查看更多</Link>
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          {topRated.map(server => <ServerCard key={server.id} server={server} />)}
        </div>
      </section>
    </div>
  )
}

function Stat({
  label,
  value,
  description,
  to,
  tone = 'gray',
}: {
  label: string
  value: string
  description: string
  to: string
  tone?: 'gray' | 'green' | 'blue' | 'amber'
}) {
  const tones = {
    gray: 'border-gray-200',
    green: 'border-green-300',
    blue: 'border-blue-300',
    amber: 'border-amber-300',
  }
  return (
    <Link to={to} className={`border bg-white p-4 hover:bg-gray-50 ${tones[tone]}`}>
      <InfoTooltip description={description}>
        <span className="text-sm text-gray-500">{label}</span>
      </InfoTooltip>
      <p className="mt-2 text-2xl font-semibold text-gray-900">{value}</p>
    </Link>
  )
}

function MetricRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-2 last:border-0">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  )
}

function EmptyState({
  title,
  description,
  to,
  action,
}: {
  title: string
  description: string
  to: string
  action: string
}) {
  return (
    <div className="border border-gray-200 bg-white px-5 py-10 text-center">
      <h2 className="font-semibold text-gray-900">{title}</h2>
      <p className="mx-auto mt-2 max-w-xl text-sm text-gray-500">{description}</p>
      <Link to={to} className="mt-4 inline-block text-sm font-medium text-blue-700 hover:underline">
        {action}
      </Link>
    </div>
  )
}
