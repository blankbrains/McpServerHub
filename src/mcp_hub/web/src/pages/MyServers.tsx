import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  ApiRequestError,
  apiDelete,
  apiGet,
  apiPost,
  favoriteServer,
  getFavoriteServers,
  getAuthState,
  installServer,
} from '../api/client'
import StatusBadge from '../components/StatusBadge'

interface TrackedServer {
  server_id: string
  name: string
  description: string
  status: string
  running: boolean
  enabled: boolean
  pid: number | null
  location: string
  uptime_seconds: number
  reliability_score: number
  call_count_7d: number
  token_consumption: number
  security_level: string
  install_command: string
}

type TabId = 'installed' | 'tracked' | 'favorites'

function fmtNum(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

function fmtTokens(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

function fmtUptime(s: number): string {
  if (s <= 0) return '-'
  const d = Math.floor(s / 86400)
  const h = Math.floor((s % 86400) / 3600)
  const m = Math.floor((s % 3600) / 60)
  if (d > 0) return `${d}d${h}h`
  if (h > 0) return `${h}h${m}m`
  return `${m}m`
}

export default function MyServers() {
  const [servers, setServers] = useState<TrackedServer[]>([])
  const [favorites, setFavorites] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<TabId>('installed')
  const [installing, setInstalling] = useState<Set<string>>(new Set())
  const [restarting, setRestarting] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [batchActing, setBatchActing] = useState(false)
  const [errorMsg, setErrorMsg] = useState('')
  const [warningMsg, setWarningMsg] = useState('')
  const [updates, setUpdates] = useState<Set<string>>(new Set())
  const [viewMode, setViewMode] = useState<'track' | 'manage'>('track')
  const [msg, setMsg] = useState('')

  const load = async () => {
    if (!getAuthState().token) {
      setServers([])
      setErrorMsg('请先登录后查看和管理自己的 Server')
      setLoading(false)
      return
    }

    setErrorMsg('')
    setWarningMsg('')
    try {
      const configResult = await apiGet<any[]>('/config/user-servers')
      getFavoriteServers()
        .then(result => setFavorites((result.data || []).map(server => server.id)))
        .catch(() => setFavorites([]))
      let monitorServers: any[] = []
      try {
        const monitorResult = await apiGet<any>('/monitor/dashboard')
        monitorServers = monitorResult.data?.servers || []
      } catch {
        setWarningMsg('监控数据暂时不可用，正在显示已保存的追踪配置')
      }
      const monitorById = new Map(
        monitorServers.map((server: any) => [server.server_id, server])
      )
      const userServers = (configResult.data || []).map((config: any) => {
        const serverId = config.hub_id || config.name
        const monitor: any = monitorById.get(serverId) || {}
        return {
          server_id: serverId,
          name: monitor.name || config.name || serverId,
          description: monitor.description || '',
          status: monitor.status || 'not_installed',
          running: monitor.running || false,
          enabled: config.enabled !== false,
          pid: monitor.pid || null,
          location: monitor.location || 'N/A',
          uptime_seconds: monitor.uptime_seconds || 0,
          reliability_score: monitor.reliability_score || 0,
          call_count_7d: monitor.call_count_7d || 0,
          token_consumption: monitor.token_consumption || 0,
          security_level: monitor.security_level || 'unreviewed',
          install_command: monitor.install_command || '',
        }
      })
      setServers(userServers)
    } catch (error) {
      setServers([])
      setErrorMsg(
        error instanceof ApiRequestError && error.status === 401
          ? '登录状态已失效，请重新登录'
          : '加载 Server 列表失败'
      )
    }
    finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    if (!getAuthState().token) return
    apiGet<{ updates: Array<{ server_id: string }> }>('/servers/check-updates')
      .then(r => {
        if (r.data?.updates) {
          setUpdates(new Set(r.data.updates.map(update => update.server_id)))
        }
      })
      .catch(() => {})
  }, [])

  const handleAction = async (sid: string, action: 'start' | 'stop') => {
    try {
      await apiPost(`/servers/${encodeURIComponent(sid)}/${action}`)
      load()
    } catch { setErrorMsg(`${action === 'start' ? '启动' : '停止'} ${sid} 失败`) }
  }

  const handleRestart = async (sid: string) => {
    setRestarting(prev => new Set([...prev, sid]))
    try {
      await apiPost(`/servers/${encodeURIComponent(sid)}/stop`)
      // 等待进程完全停止
      await new Promise(r => setTimeout(r, 1500))
      await apiPost(`/servers/${encodeURIComponent(sid)}/start`)
      load()
    } catch { setErrorMsg(`重启 ${sid} 失败`) }
    finally {
      setRestarting(prev => { const n = new Set(prev); n.delete(sid); return n })
    }
  }

  const toggleEnabled = async (sid: string, current: boolean) => {
    if (!getAuthState().token) return
    // 先乐观更新 UI
    const prevEnabled = current
    setServers(prev => prev.map(s =>
      (s.server_id === sid) ? { ...s, enabled: !current } : s
    ))
    try {
      const result = await apiPost('/config/user-servers/toggle', {
        server_id: sid,
        enabled: !current,
      })
      if (!result.success) throw new Error('Toggle request was rejected')
    } catch {
      // 回滚乐观更新
      setServers(prev => prev.map(s =>
        (s.server_id === sid) ? { ...s, enabled: prevEnabled } : s
      ))
      setErrorMsg(`切换 ${sid} 状态失败`)
    }
  }

  const handleInstall = async (sid: string) => {
    setInstalling(prev => new Set([...prev, sid]))
    try {
      await installServer(sid)
      load()
    } catch {
      setErrorMsg(`安装 ${sid} 失败`)
    } finally {
      setInstalling(prev => { const n = new Set(prev); n.delete(sid); return n })
    }
  }

  const persistFavoriteState = (sid: string, favorited: boolean) => {
    setFavorites(prev => {
      return favorited
        ? [...new Set([...prev, sid])]
        : prev.filter(favoriteId => favoriteId !== sid)
    })
  }

  const toggleFavorite = async (sid: string): Promise<boolean | null> => {
    try {
      const result = await favoriteServer(sid)
      const favorited = Boolean(result.favorited)
      persistFavoriteState(sid, favorited)
      return favorited
    } catch {
      setErrorMsg('收藏操作失败，请检查登录状态后重试')
      return null
    }
  }

  const handleRemove = async (sid: string) => {
    if (tab === 'favorites') {
      if (!window.confirm(`确定要取消收藏 "${sid}" 吗？`)) return
      const favorited = await toggleFavorite(sid)
      if (favorited) {
        setErrorMsg('取消收藏未成功，收藏状态已刷新')
      }
      return
    }
    if (!window.confirm(`确定要移除 "${sid}" 吗？`)) return
    try {
      await apiDelete(`/config/user-servers/${encodeURIComponent(sid)}`)
      load()
    } catch { setErrorMsg(`移除 ${sid} 失败`) }
  }

  // === 批量操作 ===
  const toggleSelect = (sid: string) => {
    setSelected(prev => {
      const n = new Set(prev)
      if (n.has(sid)) { n.delete(sid) } else { n.add(sid) }
      return n
    })
  }

  const toggleSelectAll = (list: TrackedServer[]) => {
    const allIds = list.map(s => s.server_id)
    if (allIds.every(id => selected.has(id))) {
      setSelected(new Set())
    } else {
      setSelected(new Set(allIds))
    }
  }

  const batchAction = async (action: string) => {
    if (selected.size === 0) return
    if (action === 'delete' && !window.confirm(`确定要删除选中的 ${selected.size} 个 Server 吗？`)) return
    setBatchActing(true)
    const ids = [...selected]
    let failed = 0
    for (const sid of ids) {
      try {
        if (action === 'enable' || action === 'disable') {
          const enabled = action === 'enable'
          const result = await apiPost('/config/user-servers/toggle', {
            server_id: sid,
            enabled,
          })
          if (!result.success) throw new Error('Toggle request was rejected')
        } else if (action === 'start' || action === 'stop') {
          await apiPost(`/servers/${encodeURIComponent(sid)}/${action}`)
        } else if (action === 'delete') {
          await apiDelete(`/config/user-servers/${encodeURIComponent(sid)}`)
        }
      } catch { failed++ }
    }
    setSelected(new Set())
    setBatchActing(false)
    if (ids.length > 0) await load()
    if (failed > 0) {
      setErrorMsg(`批量操作完成，但 ${failed}/${ids.length} 个 Server 操作失败`)
    }
  }

  const installed = servers.filter(s => s.status !== 'not_installed')
  const tracked = servers.filter(s => s.status === 'not_installed')
  const favServers = servers.filter(s => favorites.includes(s.server_id))

  const tabCounts: Record<TabId, number> = {
    installed: installed.length,
    tracked: tracked.length,
    favorites: favServers.length,
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  const currentList = tab === 'installed' ? installed : tab === 'tracked' ? tracked : favServers
  const isInstalled = tab === 'installed' || tab === 'favorites'

  const renderList = (list: TrackedServer[]) => (
    <div className="space-y-2">
      {list.length === 0 ? (
        <div className="text-center py-12 text-gray-400 text-sm">
          {tab === 'tracked' ? '没有追踪中的 Server，去市场添加或上传配置' :
           tab === 'favorites' ? '还没有收藏任何 Server' :
           '没有已安装的 Server，请上传配置或去市场安装'}
        </div>
      ) : list.map((s) => (
        <div key={s.server_id} className={`bg-white rounded-xl border p-4 flex items-center gap-3 hover:border-gray-300 transition-colors ${
          selected.has(s.server_id) ? 'border-blue-400 bg-blue-50' : 'border-gray-200'
        }`}>
          {/* 选择框（非收藏 tab） */}
          {tab !== 'favorites' && (
            <input type="checkbox" checked={selected.has(s.server_id)} onChange={() => toggleSelect(s.server_id)}
              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 flex-shrink-0" />
          )}
          {/* 状态 */}
          <StatusBadge status={s.running ? 'running' : s.status} />
          {/* Server 信息 */}
          <div className="flex-1 min-w-0">
            <Link to={`/servers/${encodeURIComponent(s.server_id)}`} className="font-medium text-gray-900 hover:text-blue-600 truncate block">
              {s.name || s.server_id}
              {updates.has(s.server_id) && (
                <span className="ml-1.5 inline-flex items-center px-1.5 py-0.5 text-[10px] bg-orange-100 text-orange-700 rounded-full font-medium">🆕</span>
              )}
            </Link>
            <div className="flex items-center gap-3 text-xs text-gray-400 mt-0.5">
              <span title="7 日调用次数">📞 {fmtNum(s.call_count_7d || 0)}</span>
              <span title="Token 消耗">🔤 {fmtTokens(s.token_consumption || 0)}</span>
              {s.uptime_seconds > 0 && <span title="运行时长">⏱ {fmtUptime(s.uptime_seconds)}</span>}
              <span title="可靠性评分">📊 {s.reliability_score || 0}%</span>
            </div>
          </div>
          {/* 操作按钮 */}
          <div className="flex items-center gap-1.5 flex-shrink-0">
            {isInstalled ? (
              <>
                {s.running ? (
                  <>
                    <button onClick={() => handleAction(s.server_id, 'stop')}
                      className="px-2.5 py-1.5 bg-yellow-100 text-yellow-700 rounded-lg text-xs font-medium hover:bg-yellow-200">⏹</button>
                    <button onClick={() => handleRestart(s.server_id)} disabled={restarting.has(s.server_id)}
                      className="px-2.5 py-1.5 bg-blue-100 text-blue-700 rounded-lg text-xs font-medium hover:bg-blue-200 disabled:opacity-50">
                      {restarting.has(s.server_id) ? '⏳' : '🔄'}
                    </button>
                  </>
                ) : (
                  <button onClick={() => handleAction(s.server_id, 'start')}
                    className="px-2.5 py-1.5 bg-green-100 text-green-700 rounded-lg text-xs font-medium hover:bg-green-200">▶</button>
                )}
                <button onClick={() => toggleEnabled(s.server_id, !!s.enabled)}
                  className={`px-2 py-1 rounded-lg text-xs font-medium ${s.enabled !== false ? 'bg-green-100 text-green-700 hover:bg-red-100' : 'bg-gray-100 text-gray-400 hover:bg-green-100'}`}
                  title={s.enabled !== false ? '已启用（点击禁用）' : '已禁用（点击启用）'}>
                  {s.enabled !== false ? '🟢' : '⭕'}
                </button>
              </>
            ) : (
              <button onClick={() => handleInstall(s.server_id)}
                disabled={installing.has(s.server_id)}
                className="px-3 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50">
                {installing.has(s.server_id) ? '安装中...' : '📥 安装'}
              </button>
            )}
            <Link to={`/servers/${encodeURIComponent(s.server_id)}`}
              className="px-2.5 py-1.5 bg-gray-100 text-gray-600 rounded-lg text-xs font-medium hover:bg-gray-200">详情</Link>
            <button onClick={() => handleRemove(s.server_id)}
              className="px-2 py-1.5 text-xs text-red-400 hover:text-red-600 hover:bg-red-50 rounded">✕</button>
          </div>
        </div>
      ))}
    </div>
  )

  return (
    <div className="max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📦 我的 Server</h1>
          <p className="text-sm text-gray-500">共 {servers.length} 个（{installed.length} 已安装 / {tracked.length} 追踪 / {favorites.length} 收藏）</p>
        </div>
        <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">去市场 →</Link>
      </div>
      {errorMsg && (
        <div className="p-2 bg-red-50 text-red-700 rounded-lg text-sm flex items-center justify-between">
          <span>{errorMsg}</span>
          <button onClick={() => setErrorMsg('')} className="text-red-400 hover:text-red-600 ml-2">✕</button>
        </div>
      )}
      {warningMsg && (
        <div className="p-2 bg-yellow-50 text-yellow-800 rounded-lg text-sm flex items-center justify-between">
          <span>{warningMsg}</span>
          <button onClick={() => setWarningMsg('')} className="text-yellow-600 hover:text-yellow-800 ml-2">×</button>
        </div>
      )}

      {/* 视图切换 */}
      <div className="flex gap-2">
        <button
          onClick={() => setViewMode('track')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            viewMode === 'track'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200'
          }`}
        >
          📋 配置追踪
        </button>
        <button
          onClick={() => setViewMode('manage')}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            viewMode === 'manage'
              ? 'bg-blue-600 text-white'
              : 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 hover:bg-gray-200'
          }`}
        >
          ⚙️ 进程管理
        </button>
      </div>

      {viewMode === 'manage' && (<>
      {/* Tabs + Batch Bar */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="flex gap-1 bg-gray-100 rounded-lg p-1">
          {([
            ['installed', '已安装'],
            ['tracked', '追踪中'],
            ['favorites', '⭐ 收藏'],
          ] as [TabId, string][]).map(([id, label]) => (
            <button key={id} onClick={() => { setTab(id); setSelected(new Set()) }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === id ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
              aria-pressed={tab === id}>
              {label} ({tabCounts[id]})
            </button>
          ))}
        </div>

        {/* 批量操作栏 */}
        {selected.size > 0 && tab !== 'favorites' && (
          <div className="flex items-center gap-1.5 bg-blue-50 rounded-lg px-3 py-1.5 border border-blue-200">
            <span className="text-xs text-blue-700 font-medium mr-1">已选 {selected.size}</span>
            {tab === 'installed' && (
              <>
                <button onClick={() => batchAction('start')} disabled={batchActing}
                  className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50">▶ 启动</button>
                <button onClick={() => batchAction('stop')} disabled={batchActing}
                  className="px-2 py-1 text-xs bg-yellow-100 text-yellow-700 rounded hover:bg-yellow-200 disabled:opacity-50">⏹ 停止</button>
              </>
            )}
            <button onClick={() => batchAction('enable')} disabled={batchActing}
              className="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200 disabled:opacity-50">🟢 启用</button>
            <button onClick={() => batchAction('disable')} disabled={batchActing}
              className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded hover:bg-gray-200 disabled:opacity-50">⭕ 禁用</button>
            <button onClick={() => batchAction('delete')} disabled={batchActing}
              className="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200 disabled:opacity-50">🗑 删除</button>
          </div>
        )}
      </div>

      {/* 全选（非收藏 tab） */}
      {tab !== 'favorites' && currentList.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <input type="checkbox" checked={currentList.length > 0 && currentList.every(s => selected.has(s.server_id))}
            onChange={() => toggleSelectAll(currentList)} className="w-4 h-4" />
          <span>全选</span>
        </div>
      )}

      {/* Content */}
      {renderList(currentList)}
      </>)}
      {viewMode === 'track' && (
        <div className="space-y-2">
          {msg && (
            <div className="p-2 bg-green-50 text-green-700 rounded-lg text-sm flex items-center justify-between">
              <span>{msg}</span>
              <button onClick={() => setMsg('')} className="text-green-400 hover:text-green-600 ml-2">✕</button>
            </div>
          )}
          {servers.length === 0 ? (
            <div className="text-center py-12 text-gray-400 text-sm">没有追踪的 Server</div>
          ) : servers.map((s) => (
            <div key={s.server_id} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 p-4 flex items-center justify-between hover:border-gray-300 transition-colors">
              <div className="flex items-center gap-3 min-w-0 flex-1">
                <span className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
                  s.security_level === 'verified' ? 'bg-green-500' :
                  s.security_level === 'reviewed' ? 'bg-yellow-500' :
                  s.security_level === 'blocked' ? 'bg-red-500' : 'bg-gray-400'
                }`} />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Link to={`/servers/${encodeURIComponent(s.server_id)}`} className="font-mono text-sm font-medium text-gray-900 hover:text-blue-600 truncate">
                      {s.name || s.server_id}
                    </Link>
                    {updates.has(s.server_id) && (
                      <span className="text-xs bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">🆕 有更新</span>
                    )}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5 font-mono truncate">
                    {(s as any).install_command || '命令未知'}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-2 flex-shrink-0 ml-3">
                <button
                  onClick={() => {
                    const cmd = (s as any).install_command || ''
                    if (cmd) { navigator.clipboard?.writeText(cmd); setMsg('✅ 已复制'); setTimeout(() => setMsg(''), 2000) }
                  }}
                  className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 rounded font-medium"
                  title="复制安装命令"
                >
                  📋 复制
                </button>
                <button
                  onClick={async () => {
                    await toggleFavorite(s.server_id)
                  }}
                  className={`text-xs px-2 py-1 rounded font-medium ${
                    favorites.includes(s.server_id)
                      ? 'bg-yellow-100 text-yellow-700 hover:bg-yellow-200'
                      : 'bg-gray-100 dark:bg-gray-700 text-gray-500 hover:bg-gray-200'
                  }`}
                  title={favorites.includes(s.server_id) ? '取消收藏' : '收藏'}
                >
                  {favorites.includes(s.server_id) ? '⭐' : '☆'}
                </button>
                <button
                  onClick={() => handleRemove(s.server_id)}
                  className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded font-medium"
                  title="取消追踪"
                >
                  👁 取消追踪
                </button>
                <Link to={`/servers/${encodeURIComponent(s.server_id)}`}
                  className="text-xs px-2 py-1 text-blue-600 hover:underline font-medium">
                  详情 →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
