import { useState, useEffect, useRef } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../api/client'

interface ServerMetric {
  server_id: string
  name: string
  description: string
  status: string
  running: boolean
  pid: number | null
  location: string
  uptime_seconds: number
  reliability_score: number
  total_checks: number
  last_check_status: string | null
  token_consumption: number
  call_count_7d: number
  rating: number
  version: string
  security_level: string
}

interface DashboardData {
  summary: {
    total_servers: number
    running: number
    stopped: number
    error: number
    healthy: number
    total_calls_7d: number
    total_token_consumption: number
    avg_reliability: number
  }
  servers: ServerMetric[]
}

function fmtUptime(seconds: number): string {
  if (seconds <= 0) return '-'
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (d > 0) return `${d}d ${h}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

function fmtTokens(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

function Bar({ value, max, color }: { value: number; max: number; color: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="w-full bg-gray-100 rounded-full h-1.5">
      <div className={`h-1.5 rounded-full transition-all duration-500 ${color}`} style={{ width: `${pct}%` }} />
    </div>
  )
}

export default function MonitorDashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [sortField, setSortField] = useState<string>('reliability_score')
  const [sortAsc, setSortAsc] = useState(false)
  const [search, setSearch] = useState('')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  const errorCountRef = useRef(0)

  const load = async (manual = false) => {
    if (manual) setRefreshing(true)
    try {
      const r = await apiGet<DashboardData>('/monitor/dashboard')
      if (r.data) { setData(r.data); errorCountRef.current = 0 }
    } catch {
      errorCountRef.current++
      if (errorCountRef.current >= 3 && data === null) {
        setErrorMsg('监控数据加载失败，请检查服务是否正常运行')
      }
    } finally { setLoading(false); if (manual) setTimeout(() => setRefreshing(false), 500) }
  }

  // 基础间隔 10 秒，错误后退避 (最多 60 秒)
  const getInterval = () => Math.min(10 * Math.pow(2, errorCountRef.current), 60) * 1000

  useEffect(() => {
    load()
    let timer: ReturnType<typeof setTimeout>
    const scheduleNext = () => {
      timer = setTimeout(() => { load(false); scheduleNext() }, getInterval())
    }
    scheduleNext()
    return () => clearTimeout(timer)
  }, [])

  const toggleSort = (field: string) => {
    if (sortField === field) setSortAsc(!sortAsc)
    else { setSortField(field); setSortAsc(false) }
  }

  const sorted = data?.servers
    ? [...data.servers].filter(s => search ? s.server_id.toLowerCase().includes(search.toLowerCase()) : true)
      .sort((a, b) => {
        const va = (a as any)[sortField] ?? 0
        const vb = (b as any)[sortField] ?? 0
        return sortAsc ? (va > vb ? 1 : -1) : (va < vb ? 1 : -1)
      })
    : []

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="text-gray-400 text-lg">加载监控大屏...</div></div>
  }

  const s = data?.summary

  return (
    <div className={`space-y-6 transition-opacity duration-300 ${refreshing ? 'opacity-40' : 'opacity-100'}`}>
      {/* 标题 */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📈 监控大屏</h1>
          <p className="text-sm text-gray-500">所有 MCP Server 运行状态、性能指标与资源位置总览（每 10 秒自动刷新）</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => load(true)} disabled={refreshing}
            className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${refreshing ? 'bg-blue-100 text-blue-600 animate-pulse' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {refreshing ? '⏳ 刷新中...' : '🔄 刷新'}
          </button>
          <Link to="/my-servers" className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">管理 Server</Link>
        </div>
      </div>

      {/* 摘要卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        <SummaryCard label="总 Server" value={String(s?.total_servers ?? 0)} icon="📦" color="gray" />
        <SummaryCard label="运行中" value={String(s?.running ?? 0)} icon="🟢" color="green" />
        <SummaryCard label="已停止" value={String(s?.stopped ?? 0)} icon="⏹" color="gray" />
        <SummaryCard label="异常" value={String(s?.error ?? 0)} icon="🔴" color="red" />
        <SummaryCard label="7 天调用" value={String(s?.total_calls_7d ?? 0)} icon="📞" color="blue" />
        <SummaryCard label="Token 总量" value={fmtTokens(s?.total_token_consumption ?? 0)} icon="📊" color="purple" />
        <SummaryCard label={`平均可靠性 ${s?.avg_reliability ?? 0}`} value="" icon="🏆" color={s && s.avg_reliability >= 90 ? 'green' : s && s.avg_reliability >= 60 ? 'yellow' : 'red'} />
      </div>

      {/* 健康分布条 */}
      {data && (
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <div className="flex items-center gap-1 text-xs text-gray-500 mb-1.5">
            <span className="w-16">健康分布</span>
            <div className="flex-1 flex gap-0.5 h-3 rounded-full overflow-hidden">
              {s!.running > 0 && <div className="bg-green-500 transition-all" style={{ flex: s!.running }} title={`运行中 ${s!.running}`} />}
              {s!.stopped > 0 && <div className="bg-gray-300 transition-all" style={{ flex: s!.stopped }} title={`已停止 ${s!.stopped}`} />}
              {(s!.error ?? 0) > 0 && <div className="bg-red-500 transition-all" style={{ flex: s!.error }} title={`异常 ${s!.error}`} />}
            </div>
          </div>
          <div className="flex gap-4 text-xs text-gray-400">
            <span>🟢 运行 {s!.running}</span>
            <span>⏹ 停止 {s!.stopped}</span>
            {(s!.error ?? 0) > 0 && <span>🔴 异常 {s!.error}</span>}
            <span>✅ 健康 {s!.healthy}</span>
          </div>
        </div>
      )}

      {/* 搜索过滤 */}
      <div className="flex items-center gap-3">
        <input type="text" value={search} onChange={e => setSearch(e.target.value)}
          placeholder="搜索 Server ID..."
          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" />
      </div>

      {/* Server 列表 */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <Th onClick={() => toggleSort('server_id')} active={sortField === 'server_id'} asc={sortAsc}>Server</Th>
                <Th onClick={() => toggleSort('running')} active={sortField === 'running'} asc={sortAsc}>状态</Th>
                <Th>位置 / PID</Th>
                <Th onClick={() => toggleSort('uptime_seconds')} active={sortField === 'uptime_seconds'} asc={sortAsc}>运行时长</Th>
                <Th onClick={() => toggleSort('call_count_7d')} active={sortField === 'call_count_7d'} asc={sortAsc}>调用(7d)</Th>
                <Th onClick={() => toggleSort('token_consumption')} active={sortField === 'token_consumption'} asc={sortAsc}>Token</Th>
                <Th onClick={() => toggleSort('reliability_score')} active={sortField === 'reliability_score'} asc={sortAsc}>可靠性</Th>
                <Th onClick={() => toggleSort('total_checks')} active={sortField === 'total_checks'} asc={sortAsc}>检查</Th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {sorted.length === 0 ? (
                <tr><td colSpan={8} className="p-8 text-center text-gray-400">暂无数据</td></tr>
              ) : sorted.map(srv => {
                const maxCalls = Math.max(...sorted.map(s => s.call_count_7d), 1)
                const maxTokens = Math.max(...sorted.map(s => s.token_consumption), 1)
                return (
                  <tr key={srv.server_id} className="hover:bg-gray-50 transition-colors">
                    <td className="p-3">
                      <Link to={`/servers/${encodeURIComponent(srv.server_id)}`} className="text-blue-600 hover:text-blue-800 font-medium">
                        {srv.name}
                      </Link>
                      <p className="text-xs text-gray-400 truncate max-w-[200px]">{srv.description || srv.server_id}</p>
                    </td>
                    <td className="p-3">
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${
                        srv.running ? 'bg-green-100 text-green-700' : srv.status === 'error' ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-500'
                      }`}>
                        {srv.running ? '🟢 运行' : srv.status === 'error' ? '🔴 异常' : '⏹ 停止'}
                      </span>
                    </td>
                    <td className="p-3 text-xs text-gray-500 max-w-[200px] truncate" title={srv.location}>
                      <span className="font-mono">{srv.pid ? `PID ${srv.pid}` : '-'}</span>
                      <p className="truncate">{srv.location !== 'N/A' ? srv.location : '-'}</p>
                    </td>
                    <td className="p-3 text-xs text-gray-600">{fmtUptime(srv.uptime_seconds)}</td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium w-8 text-right">{srv.call_count_7d}</span>
                        <div className="flex-1 max-w-[80px]"><Bar value={srv.call_count_7d} max={maxCalls} color="bg-blue-500" /></div>
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-medium w-12 text-right">{fmtTokens(srv.token_consumption)}</span>
                        <div className="flex-1 max-w-[80px]"><Bar value={srv.token_consumption} max={maxTokens} color="bg-purple-500" /></div>
                      </div>
                    </td>
                    <td className="p-3">
                      <span className={`text-xs font-medium ${
                        srv.reliability_score >= 90 ? 'text-green-600' : srv.reliability_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {srv.reliability_score}
                      </span>
                      <div className="max-w-[60px]"><Bar value={srv.reliability_score} max={100} color={
                        srv.reliability_score >= 90 ? 'bg-green-500' : srv.reliability_score >= 60 ? 'bg-yellow-500' : 'bg-red-500'
                      } /></div>
                    </td>
                    <td className="p-3 text-xs text-gray-500">{srv.total_checks}</td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* 底部统计 */}
      {data && (
        <div className="text-xs text-gray-400 text-center">
          共监控 {s?.total_servers} 个 Server · {s?.running} 运行 · {s?.stopped} 停止 · {s?.error ?? 0} 异常 ·
          7 天总调用 {s?.total_calls_7d} 次 · Token 总消耗 {fmtTokens(s?.total_token_consumption ?? 0)}
          <span className="ml-2">🔄 每 10 秒自动刷新</span>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, icon, color }: { label: string; value: string; icon: string; color: string }) {
  const colors: Record<string, string> = {
    green: 'bg-green-50 border-green-200',
    red: 'bg-red-50 border-red-200',
    blue: 'bg-blue-50 border-blue-200',
    purple: 'bg-purple-50 border-purple-200',
    gray: 'bg-gray-50 border-gray-200',
    yellow: 'bg-yellow-50 border-yellow-200',
  }
  return (
    <div className={`rounded-xl border p-3 ${colors[color] || colors.gray}`}>
      <p className="text-xs text-gray-500 mb-0.5">{icon} {label}</p>
      {value && <p className="text-lg font-bold text-gray-900">{value}</p>}
    </div>
  )
}

function Th({ children, onClick, active, asc }: { children: React.ReactNode; onClick?: () => void; active?: boolean; asc?: boolean }) {
  return (
    <th
      onClick={onClick ? onClick : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick() } } : undefined}
      tabIndex={onClick ? 0 : undefined}
      role={onClick ? 'columnheader button' : 'columnheader'}
      aria-sort={active ? (asc ? 'ascending' : 'descending') : undefined}
      className={`p-3 text-left text-xs font-medium ${onClick ? 'cursor-pointer select-none focus:outline-none focus:ring-2 focus:ring-blue-400 focus:rounded' : ''} ${active ? 'text-blue-600' : 'text-gray-500'} ${onClick ? 'hover:text-gray-700' : ''}`}
    >
      {children} {active ? (asc ? '↑' : '↓') : ''}
    </th>
  )
}
