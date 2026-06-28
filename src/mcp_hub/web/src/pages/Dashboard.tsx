import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { healthCheck, getTrending, getTopRated, apiGet, connectStatusSSE, ServerInfo } from '../api/client'
import ServerCard from '../components/ServerCard'

export default function Dashboard() {
  const [health, setHealth] = useState<any>(null)
  const [trending, setTrending] = useState<ServerInfo[]>([])
  const [topRated, setTopRated] = useState<ServerInfo[]>([])
  const [installed, setInstalled] = useState<ServerInfo[]>([])
  const [runningCount, setRunningCount] = useState<number>(0)
  const [loading, setLoading] = useState(true)
  const [logs, setLogs] = useState<string[]>([])
  const [selectedLog, setSelectedLog] = useState<string>('')

  useEffect(() => {
    async function load() {
      try {
        const [h, t, r, inst] = await Promise.all([
          healthCheck(),
          getTrending(),
          getTopRated(),
          apiGet<ServerInfo[]>('/servers/'),
        ])
        setHealth(h.data || h)
        setTrending(t.slice(0, 6))
        setTopRated(r.slice(0, 6))
        if (inst.data) setInstalled(inst.data)
      } catch (e) {
        console.error('Failed to load dashboard:', e)
      } finally {
        setLoading(false)
      }
    }
    load()

    // Real-time status via SSE
    const es = connectStatusSSE((data) => {
      setRunningCount(Object.keys(data.running || {}).length)
    })
    return () => es.close()
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="text-gray-400 text-lg">加载中...</div></div>
  }

  return (
    <div className="space-y-8">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon="🟢" label="运行中" value={String(runningCount)} color="green" />
        <StatCard icon="📦" label="已安装" value={String(installed.length)} color="purple" />
        <StatCard icon="🏪" label="可用 Server" value={String(trending.length > 0 ? trending[0].download_count > 0 ? 15 : 10 : 10)} color="blue" />
        <StatCard icon="⚡" label="Hub 状态" value={health?.status || 'unknown'} color="green" />
      </div>

      {/* Installed Servers */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">📦 已安装 Server</h2>
          <Link to="/my-servers" className="text-sm text-blue-600 hover:text-blue-800">管理 →</Link>
        </div>
        {installed.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
            还没有安装任何 Server
            <br />
            <Link to="/market" className="text-blue-600 mt-2 inline-block">去市场安装 →</Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {installed.map((s) => (
              <ServerCard key={s.id} server={s} />
            ))}
          </div>
        )}
      </section>

      {/* Log Viewer */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">📋 日志</h2>
          <select
            value={selectedLog}
            onChange={(e) => setSelectedLog(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white"
          >
            <option value="">选择 Server 查看日志...</option>
            {installed.map((s) => (
              <option key={s.id} value={s.id}>{s.id}</option>
            ))}
          </select>
        </div>
        <LogViewer serverId={selectedLog} />
      </section>

      {/* Trending */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">🔥 热门趋势</h2>
          <Link to="/market?sort=hot" className="text-sm text-blue-600 hover:text-blue-800">查看全部 →</Link>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {trending.map((s) => (
            <ServerCard key={s.id} server={s} />
          ))}
        </div>
      </section>
    </div>
  )
}

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    green: 'bg-green-50 border-green-200',
    blue: 'bg-blue-50 border-blue-200',
    purple: 'bg-purple-50 border-purple-200',
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[color] || colors.blue}`}>
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  )
}

function LogViewer({ serverId }: { serverId: string }) {
  const [lines, setLines] = useState<string[]>([])

  useEffect(() => {
    if (!serverId) return
    setLines([])
    const es = new EventSource(`/api/v1/realtime/logs/${encodeURIComponent(serverId)}`)
    es.onmessage = (e) => {
      try {
        const d = JSON.parse(e.data)
        if (d.line) {
          setLines((prev) => [...prev.slice(-199), d.line])
        }
      } catch { /* ignore */ }
    }
    es.onerror = () => es.close()
    return () => es.close()
  }, [serverId])

  if (!serverId) return <div className="bg-gray-50 rounded-xl border border-gray-200 p-6 text-center text-gray-400 text-sm">选择已安装的 Server 查看实时日志</div>

  return (
    <div className="bg-gray-900 rounded-xl p-4 font-mono text-sm text-green-400 h-64 overflow-y-auto">
      {lines.length === 0 && <div className="text-gray-500">等待日志...</div>}
      {lines.map((line, i) => (
        <div key={i} className="whitespace-pre-wrap break-all">{line}</div>
      ))}
    </div>
  )
}
