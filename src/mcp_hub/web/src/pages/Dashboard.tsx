import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  healthCheck, getTrending, getTopRated, apiGet, connectStatusSSE,
  ServerInfo, downloadConfig, getAuthHeaders, getAuthState, getFavoriteServers, uploadConfig, getMonitorSummary, getTopReliable,
} from '../api/client'
import ServerCard from '../components/ServerCard'
import LogViewer from '../components/LogViewer'

export default function Dashboard() {
  const auth = getAuthState()
  const isAuthenticated = Boolean(auth.token)
  const userId = auth.userId
  const [health, setHealth] = useState<any>(null)
  const [trending, setTrending] = useState<ServerInfo[]>([])
  const [topRated, setTopRated] = useState<ServerInfo[]>([])
  const [installed, setInstalled] = useState<ServerInfo[]>([])
  const [trackedServers, setTrackedServers] = useState<any[]>([])  // 来自 monitor API 的所有追踪 Server
  const [userServers, setUserServers] = useState<any[]>([])  // 来自 /config/user-servers 的用户追踪 Server（SaaS 概览）
  const [runningCount, setRunningCount] = useState<number>(0)
  const [totalAvailable, setTotalAvailable] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedLog, setSelectedLog] = useState<string>('')
  const [logSearchQuery, setLogSearchQuery] = useState('')
  const [logSearching, setLogSearching] = useState(false)
  const [logResults, setLogResults] = useState<any[]>([])
  const [favorites, setFavorites] = useState<string[]>([])
  const [recent, setRecent] = useState<ServerInfo[]>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_recent') || '[]') } catch { return [] }
  })
  const [uploadResult, setUploadResult] = useState<any>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_upload_result') || 'null') } catch { return null }
  })
  // Monitor states
  const [monitorSummary, setMonitorSummary] = useState<any>(null)
  const [topReliable, setTopReliable] = useState<any[]>([])
  const [recommendations, setRecommendations] = useState<ServerInfo[]>([])
  const [updateServerIds, setUpdateServerIds] = useState<Set<string>>(new Set())

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
        // 从 monitor API 加载所有追踪 Server（含已安装和未安装但追踪的）
        if (monitor?.data?.servers) {
          setTrackedServers(monitor.data.servers)
        }
        // 总追踪数用 monitor API
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
    // 加载个性化推荐
    if (userId) {
      apiGet<ServerInfo[]>(`/market/recommendations?user_id=${encodeURIComponent(userId)}&limit=6`)
        .then(r => setRecommendations(r.data || [])).catch(() => setRecommendations([]))
    }

    const es = connectStatusSSE((data) => {
      setRunningCount(Object.keys(data.running || {}).length)
    })
    return () => es.close()
  }, [])

  // Recent items are local UI history. Favorites are account data and load from the API below.
  useEffect(() => {
    const handler = () => {
      try {
        const rec = JSON.parse(localStorage.getItem('mcp_hub_recent') || '[]')
        setRecent(rec)
      } catch {}
    }
    window.addEventListener('storage', handler)
    return () => window.removeEventListener('storage', handler)
  }, [])

  // 加载用户追踪的 Server（SaaS 概览数据源）
  useEffect(() => {
    if (isAuthenticated) {
      apiGet<any[]>('/config/user-servers')
        .then(r => setUserServers(r.data || []))
        .catch(() => {})
      getFavoriteServers()
        .then(r => setFavorites((r.data || []).map(server => server.id)))
        .catch(() => setFavorites([]))
      apiGet<{ updates: Array<{ server_id: string }> }>('/servers/check-updates')
        .then(r => setUpdateServerIds(new Set((r.data?.updates || []).map(update => update.server_id))))
        .catch(() => setUpdateServerIds(new Set()))
    } else {
      setFavorites([])
    }
  }, [isAuthenticated, userId])

  const handleDownloadConfig = async () => {
    if (!isAuthenticated) {
      setError('请先登录后下载自己的配置')
      return
    }
    try {
      const blob = await downloadConfig()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'mcp-hub-config.json'; a.click()
      URL.revokeObjectURL(url)
    } catch { setError('下载配置失败，请检查服务是否正常运行') }
  }

  const handleUploadConfig = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!isAuthenticated) {
      setUploadResult({ success: false, message: '请先登录后上传配置' })
      return
    }
    try {
      const r = await uploadConfig(file)
      setUploadResult(r)
      localStorage.setItem('mcp_hub_upload_result', JSON.stringify(r))
    } catch { setUploadResult({ success: false, message: '上传失败' }) }
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

  // === SaaS 概览数据 ===
  const monitorById = new Map(
    trackedServers.map((server: any) => [server.server_id, server])
  )
  const saasServers = isAuthenticated
    ? userServers.map((config: any) => {
      const serverId = config.hub_id || config.name
      const monitor: any = monitorById.get(serverId) || {}
      return {
        ...monitor,
        id: serverId,
        server_id: serverId,
        name: monitor.name || config.name || serverId,
        security_level: monitor.security_level || 'unreviewed',
        has_update: updateServerIds.has(serverId),
      }
    })
    : []
  const trackedCount = saasServers.length
  const updateCount = saasServers.filter((s: any) => s.has_update).length
  const riskCount = saasServers.filter((s: any) => {
    const level = s.security_level
    return !level || (level !== 'verified' && level !== 'reviewed')
  }).length

  return (
    <div className="space-y-8">
      {/* === SaaS 概览（新增）=== */}
      {userId && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold mb-4">👋 欢迎, {userId}</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
              <div className="text-3xl font-bold text-blue-600">{trackedCount}</div>
              <div className="text-sm text-gray-500">已追踪</div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
              <div className="text-3xl font-bold text-yellow-500">{favorites.length}</div>
              <div className="text-sm text-gray-500">已收藏</div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
              <div className="text-3xl font-bold text-orange-500">{updateCount}</div>
              <div className="text-sm text-gray-500">有更新</div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
              <div className="text-3xl font-bold text-red-500">{riskCount}</div>
              <div className="text-sm text-gray-500">安全风险</div>
            </div>
          </div>

          {/* 最近追踪的 Server */}
          {saasServers.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm">
              <h3 className="font-semibold mb-3">📋 我的追踪 Server</h3>
              <div className="space-y-2">
                {saasServers.slice(0, 5).map((s: any) => (
                  <div key={s.server_id || s.id} className="flex items-center justify-between py-2 border-b last:border-0">
                    <div className="flex items-center gap-3">
                      <span className={`w-2 h-2 rounded-full ${s.security_level === 'verified' ? 'bg-green-500' : s.security_level === 'reviewed' ? 'bg-yellow-500' : 'bg-gray-400'}`} />
                      <span className="font-mono text-sm">{s.server_id || s.id}</span>
                      {s.has_update && <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded">🆕</span>}
                    </div>
                    <button
                      onClick={() => navigator.clipboard?.writeText(s.install_command || '')}
                      className="text-xs text-gray-400 hover:text-blue-600"
                      title="复制安装命令"
                    >
                      📋 复制
                    </button>
                  </div>
                ))}
              </div>
              {saasServers.length > 5 && (
                <Link to="/my-servers" className="text-sm text-blue-600 mt-2 inline-block">
                  查看全部 {saasServers.length} 个 →
                </Link>
              )}
            </div>
          )}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <StatCard icon="🟢" label="运行中" value={String(runningCount)} color="green" to="/my-servers" />
        <StatCard icon="📦" label="已安装" value={String(installed.length)} color="purple" to="/my-servers" />
        <StatCard icon="📋" label="配置中" value={String(totalAvailable || installed.length)} color="blue" to="/my-servers" />
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
                <button onClick={() => {
                  if (!window.confirm('确定清除本次上传结果吗？这不会删除已经保存的 Server。')) return
                  setUploadResult(null)
                  localStorage.removeItem('mcp_hub_upload_result')
                }}
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
            <button onClick={() => {
              if (!window.confirm('确定清除本浏览器中的最近查看记录吗？')) return
              localStorage.removeItem('mcp_hub_recent')
              setRecent([])
            }} className="text-sm text-gray-400 hover:text-gray-600">
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

      {/* Installed + Tracked Servers */}
      <section>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">📦 已安装 Server（{installed.length}）/ 追踪中（{trackedServers.length}）</h2>
          <Link to="/my-servers" className="text-sm text-blue-600 hover:text-blue-800">全部 {totalAvailable} 个 →</Link>
        </div>
        {installed.length === 0 && trackedServers.length === 0 ? (
          <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
            还没有安装任何 Server
            <br />
            <Link to="/market" className="text-blue-600 mt-2 inline-block">去市场安装 →</Link>
            <br />
            <span className="text-xs text-gray-400 mt-1">或 <Link to="/config" className="text-blue-600">上传 mcp.json 配置</Link></span>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {installed.map((s) => (
                <ServerCard key={s.id} server={s} />
              ))}
              {/* 追踪但未安装的 Server — 简化卡片 */}
              {trackedServers
                .filter(ts => ts.status === 'not_installed' && !installed.some(i => i.id === ts.server_id))
                .slice(0, 3)
                .map((ts) => (
                  <Link
                    key={ts.server_id}
                    to={`/servers/${encodeURIComponent(ts.server_id)}`}
                    className="block bg-white rounded-xl border border-dashed border-gray-200 p-5 hover:border-blue-200 hover:shadow-sm transition-all opacity-70 hover:opacity-100"
                  >
                    <div className="flex items-center gap-3">
                      <span className="text-gray-300 text-xl">📥</span>
                      <div>
                        <p className="font-medium text-gray-500 text-sm truncate">{ts.name || ts.server_id}</p>
                        <p className="text-xs text-gray-400">追踪中 · 未安装</p>
                      </div>
                    </div>
                  </Link>
                ))}
            </div>
            {trackedServers.filter(ts => ts.status === 'not_installed' && !installed.some(i => i.id === ts.server_id)).length > 3 && (
              <p className="text-xs text-gray-400 text-center mt-2">
                还有 {trackedServers.filter(ts => ts.status === 'not_installed' && !installed.some(i => i.id === ts.server_id)).length - 3} 个追踪中的 Server
                <Link to="/my-servers" className="text-blue-600 ml-1">查看全部 →</Link>
              </p>
            )}
          </>
        )}
      </section>

      {/* Log Viewer + Search */}
      <section>
        <div className="flex items-center justify-between mb-4 gap-4">
          <h2 className="text-lg font-semibold text-gray-900 flex-shrink-0">📋 日志</h2>
          <div className="flex items-center gap-2 flex-1">
            <select
              value={selectedLog}
              onChange={(e) => setSelectedLog(e.target.value)}
              className="px-3 py-1.5 border border-gray-300 rounded-lg text-sm bg-white"
            >
              <option value="">选择 Server...</option>
              {installed.map((s) => (
                <option key={s.id} value={s.id}>{s.id}</option>
              ))}
            </select>
            <form className="flex gap-1.5" onSubmit={async (e) => {
              e.preventDefault()
              if (!logSearchQuery.trim()) return
              setLogSearching(true); setLogResults([])
              try {
                const r = await fetch(`/api/v1/logs/search?q=${encodeURIComponent(logSearchQuery)}&lines=20`, {
                  headers: getAuthHeaders(),
                })
                const d = await r.json()
                setLogResults(d.data || [])
              } catch { setLogResults([]) }
              finally { setLogSearching(false) }
            }}>
              <input
                type="text" value={logSearchQuery} onChange={e => setLogSearchQuery(e.target.value)}
                placeholder="搜索 error、timeout..."
                className="px-2 py-1.5 border border-gray-300 rounded-lg text-xs w-36 focus:ring-1 focus:ring-blue-400 outline-none"
              />
              <button type="submit" disabled={logSearching}
                className="px-2 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs hover:bg-gray-200 disabled:opacity-50">
                {logSearching ? '搜索中...' : '搜索'}
              </button>
            </form>
          </div>
        </div>
        {logResults.length > 0 && (
          <div className="mb-3 bg-yellow-50 rounded-lg border border-yellow-200 p-3 max-h-48 overflow-y-auto space-y-1.5">
            <p className="text-xs text-yellow-700 font-medium mb-1">搜索结果: {logResults.length} 条匹配</p>
            {logResults.map((r: any, i: number) => (
              <div key={i} className="text-xs font-mono">
                <span className="text-gray-500">[{r.server}]</span>{' '}
                {r.context_before?.map((l: string, j: number) => <div key={`b${j}`} className="text-gray-300 pl-4">{l}</div>)}
                <span className="text-red-600 font-semibold">L{r.line_number}: {r.match}</span>
                {r.context_after?.map((l: string, j: number) => <div key={`a${j}`} className="text-gray-300 pl-4">{l}</div>)}
              </div>
            ))}
            <button onClick={() => {
              if (!window.confirm('确定清除当前日志搜索结果吗？')) return
              setLogResults([])
            }} className="text-xs text-gray-400 hover:text-gray-600">清除结果</button>
          </div>
        )}
        {selectedLog ? <LogViewer serverId={selectedLog} /> : (
          <div className="bg-white rounded-xl border border-gray-200 p-6 text-center text-gray-400 text-sm">
            选择一个 Server 查看实时日志，或输入关键词跨 Server 搜索
          </div>
        )}
      </section>

      {/* 个性化推荐 */}
      {recommendations.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">💡 猜你喜欢</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recommendations.slice(0, 6).map(s => (
              <Link key={s.id} to={`/servers/${encodeURIComponent(s.id)}`}
                className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-blue-300 hover:shadow-sm transition-all">
                <p className="font-medium text-gray-900 text-sm truncate">{s.id.split('/').pop()}</p>
                <p className="text-xs text-gray-400 mt-1 line-clamp-2">{s.description?.slice(0, 80) || ''}</p>
                <div className="flex items-center gap-3 mt-2 text-xs text-gray-400">
                  <span>⭐ {(s.rating || 0).toFixed(1)}</span>
                  <span>📥 {s.download_count >= 1000 ? `${(s.download_count/1000).toFixed(1)}K` : s.download_count}</span>
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}

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
