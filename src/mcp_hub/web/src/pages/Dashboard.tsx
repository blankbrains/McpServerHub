import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  healthCheck, getTrending, getTopRated, apiGet, connectStatusSSE,
  ServerInfo, downloadConfig, uploadConfig, getMonitorSummary, getTopReliable,
} from '../api/client'
import ServerCard from '../components/ServerCard'
import LogViewer from '../components/LogViewer'

export default function Dashboard() {
  const [health, setHealth] = useState<any>(null)
  const [trending, setTrending] = useState<ServerInfo[]>([])
  const [topRated, setTopRated] = useState<ServerInfo[]>([])
  const [installed, setInstalled] = useState<ServerInfo[]>([])
  const [runningCount, setRunningCount] = useState<number>(0)
  const [totalAvailable, setTotalAvailable] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedLog, setSelectedLog] = useState<string>('')
  const [favorites, setFavorites] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_favorites') || '[]') } catch { return [] }
  })
  const [recent, setRecent] = useState<ServerInfo[]>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_recent') || '[]') } catch { return [] }
  })
  const [uploadResult, setUploadResult] = useState<any>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_upload_result') || 'null') } catch { return null }
  })
  const [gatewayUrl, setGatewayUrl] = useState(window.location.origin + '/api/v1')
  // Monitor states
  const [monitorSummary, setMonitorSummary] = useState<any>(null)
  const [topReliable, setTopReliable] = useState<any[]>([])

  useEffect(() => {
    async function load() {
      try {
        const [h, t, r, inst, monitor] = await Promise.all([
          healthCheck(),
          getTrending(),
          getTopRated(),
          apiGet<ServerInfo[]>('/servers/'),
          apiGet<any>('/monitor/dashboard').catch(() => null),
        ])
        setHealth(h.data || h)
        setTrending(t.slice(0, 6))
        setTopRated(r.slice(0, 6))
        if (inst.data) setInstalled(inst.data)
        // 已安装计数用 installed API，总追踪数用 monitor API
        if (monitor?.data?.summary?.total_servers) {
          setTotalAvailable(monitor.data.summary.total_servers)
        } else {
          const healthR = await apiGet<any>('/health/servers')
          if (healthR.data?.total_available) setTotalAvailable(healthR.data.total_available)
        }
      } catch (e) {
        console.error('Failed to load dashboard:', e)
        setError('加载仪表盘数据失败，请检查网络连接或刷新页面重试')
      } finally {
        setLoading(false)
      }
    }
    load()

    // Load monitoring data
    getMonitorSummary().then(r => setMonitorSummary(r.data)).catch(() => {})
    getTopReliable(5).then(r => setTopReliable(r.data || [])).catch(() => {})

    const es = connectStatusSSE((data) => {
      setRunningCount(Object.keys(data.running || {}).length)
    })
    return () => es.close()
  }, [])

  // Listen for storage changes (favorites from other tabs)
  useEffect(() => {
    const handler = () => {
      try {
        const fav = JSON.parse(localStorage.getItem('mcp_hub_favorites') || '[]')
        setFavorites(fav)
        const rec = JSON.parse(localStorage.getItem('mcp_hub_recent') || '[]')
        setRecent(rec)
      } catch {}
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [])

  const handleDownloadConfig = async () => {
    const blob = await downloadConfig()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'mcp-hub-config.json'; a.click()
    URL.revokeObjectURL(url)
  }

  const handleUploadConfig = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const r = await uploadConfig(file)
    setUploadResult(r)
    localStorage.setItem('mcp_hub_upload_result', JSON.stringify(r))
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="text-gray-400 text-lg">加载中...</div></div>
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center space-y-3">
          <div className="text-red-500 text-lg">😵 {error}</div>
          <button onClick={() => { setError(null); setLoading(true); window.location.reload() }}
            className="px-4 py-2 text-sm text-blue-600 border border-blue-300 rounded-lg hover:bg-blue-50">
            重试
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon="🟢" label="运行中" value={String(runningCount)} color="green" to="/my-servers" />
        <StatCard icon="📦" label="已安装" value={String(installed.length)} color="purple" to="/my-servers" />
        <StatCard icon="📋" label="追踪中" value={String(totalAvailable || installed.length)} color="blue" to="/my-servers" />
        <StatCard icon="⚡" label="Hub 状态" value={health?.status || 'unknown'} color="green" to="/" />
      </div>

      {/* Monitoring Section */}
      {(monitorSummary || topReliable.length > 0) && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">📈 系统监控</h2>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {monitorSummary && (
              <div className="bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-sm text-gray-500 mb-2">健康检查总览</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-xl font-bold text-gray-900">{monitorSummary.total_health_checks}</p>
                    <p className="text-xs text-gray-400">总检查次数</p>
                  </div>
                  <div>
                    <p className={`text-xl font-bold ${monitorSummary.errors_last_24h > 0 ? 'text-red-600' : 'text-green-600'}`}>
                      {monitorSummary.errors_last_24h}
                    </p>
                    <p className="text-xs text-gray-400">24h 错误</p>
                  </div>
                  <div>
                    <p className="text-xl font-bold text-gray-900">{monitorSummary.running}</p>
                    <p className="text-xs text-gray-400">运行中</p>
                  </div>
                  <div>
                    <p className="text-xl font-bold text-gray-900">{monitorSummary.total_servers}</p>
                    <p className="text-xs text-gray-400">Server 总数</p>
                  </div>
                </div>
              </div>
            )}
            {topReliable.length > 0 && (
              <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 p-4">
                <p className="text-sm text-gray-500 mb-2">🏆 最稳定 Server</p>
                <div className="space-y-1.5">
                  {topReliable.slice(0, 5).map((s, i) => (
                    <Link key={s.server_id} to={`/servers/${encodeURIComponent(s.server_id)}`}
                      className="flex items-center justify-between px-3 py-1.5 rounded-lg hover:bg-gray-50 transition-colors"
                    >
                      <span className="text-sm text-gray-800 truncate">
                        {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : `${i + 1}.`} {s.server_id.split('/').pop()}
                      </span>
                      <span className={`text-xs font-medium ${
                        s.reliability_score >= 90 ? 'text-green-600' :
                        s.reliability_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {s.reliability_score}/100
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {/* Config Section */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">⚙️ 配置管理</h2>
          <Link to="/config" className="text-sm text-blue-600 hover:text-blue-800">管理配置 →</Link>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-4 flex-wrap">
            <button onClick={handleDownloadConfig} className="px-5 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium">
              📥 下载配置
            </button>
            <label className="px-5 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 text-sm font-medium cursor-pointer">
              📤 上传配置
              <input type="file" accept=".json" onChange={handleUploadConfig} className="hidden" />
            </label>
          </div>
          {uploadResult && (
            <div className="mt-3 p-3 bg-blue-50 rounded-lg text-sm text-blue-700 space-y-1">
              <div className="flex justify-between items-start">
                <p>{uploadResult.message || '配置上传成功'}</p>
                <button onClick={() => { setUploadResult(null); localStorage.removeItem('mcp_hub_upload_result') }}
                  className="text-blue-400 hover:text-blue-600 text-xs ml-2">✕ 清除</button>
              </div>
              {uploadResult.data?.matched?.length > 0 && (
                <div>
                  <p className="font-medium mt-2">✅ 可在 Hub 中安装的 Server：</p>
                  {uploadResult.data.matched.map((m: any) => (
                    <p key={m.local_name} className="ml-2">• {m.local_name} → 安装命令: {m.hub_install_command || m.local_command}</p>
                  ))}
                </div>
              )}
              {uploadResult.data?.unmatched?.length > 0 && (
                <div>
                  <p className="font-medium mt-2 text-yellow-700">⚠️ 未匹配到市场的 Server：</p>
                  {uploadResult.data.unmatched.slice(0, 5).map((m: any) => (
                    <p key={m.local_name} className="ml-2">• {m.local_name} ({m.local_command})</p>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </section>

      {/* Recent */}
      {recent.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">🕐 最近查看</h2>
            <button onClick={() => { localStorage.removeItem('mcp_hub_recent'); setRecent([]) }} className="text-sm text-gray-400 hover:text-gray-600">
              清除记录
            </button>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recent.map((s) => (
              <ServerCard key={s.id} server={s} />
            ))}
          </div>
        </section>
      )}

      {/* Favorites */}
      {favorites.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">⭐ 收藏的 Server</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {installed.filter((s) => favorites.includes(s.id)).map((s) => (
              <ServerCard key={s.id} server={s} />
            ))}
            {installed.filter((s) => favorites.includes(s.id)).length === 0 && (
              <div className="col-span-3 text-center py-8 text-gray-400">
                还没有收藏任何 Server，在市场页面点击 ⭐ 收藏
              </div>
            )}
          </div>
        </section>
      )}

      {/* Installed Servers */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">📦 已安装 Server（{installed.length}）</h2>
          <Link to="/my-servers" className="text-sm text-blue-600 hover:text-blue-800">全部 {totalAvailable} 个 →</Link>
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

function StatCard({ icon, label, value, color, to }: { icon: string; label: string; value: string; color: string; to?: string }) {
  const colors: Record<string, string> = {
    green: 'bg-green-50 border-green-200 hover:bg-green-100',
    blue: 'bg-blue-50 border-blue-200 hover:bg-blue-100',
    purple: 'bg-purple-50 border-purple-200 hover:bg-purple-100',
  }
  const content = (
    <div className="flex items-center gap-3">
      <span className="text-2xl">{icon}</span>
      <div>
        <p className="text-2xl font-bold text-gray-900">{value}</p>
        <p className="text-sm text-gray-500">{label}</p>
      </div>
    </div>
  )
  if (to) {
    return (
      <Link to={to} className={`rounded-xl border p-4 block transition-colors cursor-pointer ${colors[color] || colors.blue}`}>
        {content}
      </Link>
    )
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[color] || colors.blue}`}>
      {content}
    </div>
  )
}

// LogViewer 已移至 components/LogViewer.tsx，共享使用
