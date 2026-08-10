import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ApiRequestError,
  apiDelete,
  apiGet,
  apiPost,
  favoriteServer,
  getAuthState,
  getFavoriteServers,
} from '../api/client'
import InfoTooltip from '../components/InfoTooltip'
import StatusBadge from '../components/StatusBadge'

interface TrackedServer {
  server_id: string
  name: string
  description: string
  status: string
  running: boolean
  enabled: boolean
  uptime_seconds: number
  reliability_score: number
  call_count_7d: number
  token_consumption: number
  security_level: string
  install_command: string
}

interface UserServerConfig {
  name: string
  hub_id: string
  enabled: boolean
}

type TabId = 'all' | 'connected' | 'favorites'

function fmtNum(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function fmtUptime(seconds: number): string {
  if (seconds <= 0) return '-'
  const days = Math.floor(seconds / 86_400)
  const hours = Math.floor((seconds % 86_400) / 3_600)
  const minutes = Math.floor((seconds % 3_600) / 60)
  if (days > 0) return `${days}d ${hours}h`
  if (hours > 0) return `${hours}h ${minutes}m`
  return `${minutes}m`
}

function hasGatewayInventory(status: string): boolean {
  return status !== 'not_connected'
}

export default function MyServers() {
  const [servers, setServers] = useState<TrackedServer[]>([])
  const [favorites, setFavorites] = useState<Set<string>>(new Set())
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [tab, setTab] = useState<TabId>('all')
  const [query, setQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [acting, setActing] = useState<Set<string>>(new Set())
  const [batchActing, setBatchActing] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const load = async (refresh = false) => {
    if (!getAuthState().token) {
      setServers([])
      setError('请先登录后查看自己的 Server。')
      setLoading(false)
      return
    }

    if (refresh) setRefreshing(true)
    setError('')
    try {
      const [configResult, monitorResult, favoriteResult] = await Promise.all([
        apiGet<UserServerConfig[]>('/config/user-servers'),
        apiGet<{ servers: TrackedServer[] }>('/monitor/dashboard'),
        getFavoriteServers().catch(() => ({ success: true, data: [] })),
      ])
      const monitorById = new Map(
        (monitorResult.data?.servers || []).map(server => [server.server_id, server])
      )
      const merged = (configResult.data || []).map(config => {
        const serverId = config.hub_id || config.name
        const monitored = monitorById.get(serverId)
        return {
          server_id: serverId,
          name: monitored?.name || config.name || serverId,
          description: monitored?.description || '',
          status: monitored?.status || 'not_connected',
          running: monitored?.running || false,
          enabled: config.enabled !== false,
          uptime_seconds: monitored?.uptime_seconds || 0,
          reliability_score: monitored?.reliability_score || 0,
          call_count_7d: monitored?.call_count_7d || 0,
          token_consumption: monitored?.token_consumption || 0,
          security_level: monitored?.security_level || 'unreviewed',
          install_command: monitored?.install_command || '',
        }
      })
      setServers(merged)
      setFavorites(new Set((favoriteResult.data || []).map(server => server.id)))
    } catch (loadError) {
      setServers([])
      setError(
        loadError instanceof ApiRequestError && loadError.status === 401
          ? '登录状态已失效，请重新登录。'
          : 'Server 列表加载失败，请稍后重试。'
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const filteredServers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return servers.filter(server => {
      if (tab === 'connected' && !hasGatewayInventory(server.status)) return false
      if (tab === 'favorites' && !favorites.has(server.server_id)) return false
      if (!normalizedQuery) return true
      return `${server.name} ${server.server_id} ${server.description}`
        .toLowerCase()
        .includes(normalizedQuery)
    })
  }, [favorites, query, servers, tab])

  const connectedCount = servers.filter(server => hasGatewayInventory(server.status)).length
  const runningCount = servers.filter(server => server.running).length

  const withAction = async (serverId: string, action: () => Promise<void>) => {
    setActing(previous => new Set(previous).add(serverId))
    setError('')
    setNotice('')
    try {
      await action()
    } finally {
      setActing(previous => {
        const next = new Set(previous)
        next.delete(serverId)
        return next
      })
    }
  }

  const toggleEnabled = async (server: TrackedServer) => {
    await withAction(server.server_id, async () => {
      try {
        const enabled = !server.enabled
        const result = await apiPost('/config/user-servers/toggle', {
          server_id: server.server_id,
          enabled,
        })
        if (!result.success) throw new Error('toggle rejected')
        setServers(previous => previous.map(item => (
          item.server_id === server.server_id ? { ...item, enabled } : item
        )))
        setNotice(
          enabled
            ? `${server.name} 将包含在下一次配置同步中。`
            : `${server.name} 已从下一次配置同步中排除。`
        )
      } catch {
        setError(`更新 ${server.name} 的同步状态失败。`)
      }
    })
  }

  const toggleFavorite = async (server: TrackedServer) => {
    await withAction(server.server_id, async () => {
      try {
        const result = await favoriteServer(server.server_id)
        setFavorites(previous => {
          const next = new Set(previous)
          if (result.favorited) next.add(server.server_id)
          else next.delete(server.server_id)
          return next
        })
      } catch {
        setError(`更新 ${server.name} 的收藏状态失败。`)
      }
    })
  }

  const removeServer = async (server: TrackedServer) => {
    if (!window.confirm(
      `确定从你的 Hub 配置中移除“${server.name}”吗？这不会卸载本地依赖，也不会删除市场条目。`
    )) return

    await withAction(server.server_id, async () => {
      try {
        await apiDelete(`/config/user-servers/${encodeURIComponent(server.server_id)}`)
        setServers(previous => previous.filter(item => item.server_id !== server.server_id))
        setSelected(previous => {
          const next = new Set(previous)
          next.delete(server.server_id)
          return next
        })
        setNotice(`${server.name} 已从你的 Hub 配置中移除。`)
      } catch {
        setError(`移除 ${server.name} 失败。`)
      }
    })
  }

  const toggleSelected = (serverId: string) => {
    setSelected(previous => {
      const next = new Set(previous)
      if (next.has(serverId)) next.delete(serverId)
      else next.add(serverId)
      return next
    })
  }

  const toggleSelectAll = () => {
    const visibleIds = filteredServers.map(server => server.server_id)
    setSelected(previous => (
      visibleIds.every(serverId => previous.has(serverId))
        ? new Set()
        : new Set(visibleIds)
    ))
  }

  const batchUpdate = async (action: 'enable' | 'disable' | 'remove') => {
    const serverIds = [...selected]
    if (serverIds.length === 0) return
    if (
      action === 'remove'
      && !window.confirm(
        `确定从你的 Hub 配置中移除选中的 ${serverIds.length} 个 Server 吗？本地依赖不会被卸载。`
      )
    ) return

    setBatchActing(true)
    setError('')
    let failed = 0
    for (const serverId of serverIds) {
      try {
        if (action === 'remove') {
          await apiDelete(`/config/user-servers/${encodeURIComponent(serverId)}`)
        } else {
          await apiPost('/config/user-servers/toggle', {
            server_id: serverId,
            enabled: action === 'enable',
          })
        }
      } catch {
        failed += 1
      }
    }
    setBatchActing(false)
    setSelected(new Set())
    await load(true)
    if (failed > 0) setError(`${failed}/${serverIds.length} 个操作失败。`)
    else setNotice(`已完成 ${serverIds.length} 个 Server 的批量操作。`)
  }

  if (loading) {
    return <div className="py-16 text-center text-sm text-gray-500">正在读取你的 Server...</div>
  }

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">我的 Server</h1>
          <p className="mt-1 text-sm text-gray-500">
            {servers.length} 个已追踪，{connectedCount} 个已由本地 Gateway 上报，{runningCount} 个当前运行。
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => void load(true)}
            disabled={refreshing}
            className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {refreshing ? '刷新中...' : '刷新'}
          </button>
          <Link
            to="/market"
            className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            添加 Server
          </Link>
        </div>
      </header>

      <div className="border-l-4 border-blue-500 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        页面状态来自你的本地 Gateway 遥测。网页中的启用开关决定 Server 是否参与下一次
        <code className="mx-1 font-mono text-xs">mcp-hub config sync</code>
        ，不会远程启动、停止或卸载你电脑上的进程。
      </div>

      {error && <div role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {notice && <div role="status" className="border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{notice}</div>}

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-3">
        <div className="flex border border-gray-200 bg-gray-50 p-1" role="tablist">
          {([
            ['all', `全部 ${servers.length}`],
            ['connected', `已接入 ${connectedCount}`],
            ['favorites', `收藏 ${favorites.size}`],
          ] as [TabId, string][]).map(([id, label]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => {
                setTab(id)
                setSelected(new Set())
              }}
              className={`px-3 py-1.5 text-sm ${tab === id ? 'bg-white font-medium text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
            >
              {label}
            </button>
          ))}
        </div>
        <input
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="搜索名称或 ID"
          aria-label="搜索我的 Server"
          className="w-full max-w-xs rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
        />
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 border border-blue-200 bg-blue-50 px-3 py-2">
          <span className="text-sm font-medium text-blue-800">已选 {selected.size} 个</span>
          <button type="button" disabled={batchActing} onClick={() => void batchUpdate('enable')} className="rounded-md border border-blue-300 px-2 py-1 text-xs text-blue-800 hover:bg-blue-100 disabled:opacity-50">
            加入同步
          </button>
          <button type="button" disabled={batchActing} onClick={() => void batchUpdate('disable')} className="rounded-md border border-blue-300 px-2 py-1 text-xs text-blue-800 hover:bg-blue-100 disabled:opacity-50">
            排除同步
          </button>
          <button type="button" disabled={batchActing} onClick={() => void batchUpdate('remove')} className="rounded-md border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50">
            移除
          </button>
        </div>
      )}

      {filteredServers.length > 0 && (
        <label className="flex w-fit items-center gap-2 text-xs text-gray-500">
          <input
            type="checkbox"
            checked={filteredServers.every(server => selected.has(server.server_id))}
            onChange={toggleSelectAll}
          />
          选择当前列表
        </label>
      )}

      <div className="space-y-2">
        {filteredServers.map(server => {
          const busy = acting.has(server.server_id)
          return (
            <article key={server.server_id} className="border border-gray-200 bg-white p-4">
              <div className="flex flex-wrap items-start gap-3">
                <input
                  type="checkbox"
                  checked={selected.has(server.server_id)}
                  onChange={() => toggleSelected(server.server_id)}
                  aria-label={`选择 ${server.name}`}
                  className="mt-1"
                />
                <StatusBadge status={server.status} />
                <div className="min-w-0 flex-1">
                  <Link to={`/servers/${encodeURIComponent(server.server_id)}`} className="font-medium text-gray-900 hover:text-blue-700">
                    {server.name}
                  </Link>
                  <p className="mt-0.5 truncate text-xs text-gray-500">{server.server_id}</p>
                  {server.description && <p className="mt-2 line-clamp-2 text-sm text-gray-600">{server.description}</p>}
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    <InfoTooltip description="过去 7 天由当前用户设备真实上报的工具调用次数。">
                      <span>调用 {fmtNum(server.call_count_7d)}</span>
                    </InfoTooltip>
                    <InfoTooltip description="根据 MCP 请求和响应载荷估算，不等同于模型供应商账单 Token。">
                      <span>Token {fmtNum(server.token_consumption)}</span>
                    </InfoTooltip>
                    <InfoTooltip description="有真实调用时按成功调用占比计算；没有调用时显示 0。">
                      <span>成功率 {server.reliability_score}%</span>
                    </InfoTooltip>
                    {server.uptime_seconds > 0 && <span>运行 {fmtUptime(server.uptime_seconds)}</span>}
                  </div>
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void toggleEnabled(server)}
                    className={`rounded-md border px-2.5 py-1.5 text-xs font-medium disabled:opacity-50 ${server.enabled ? 'border-green-300 bg-green-50 text-green-800' : 'border-gray-300 bg-gray-50 text-gray-600'}`}
                    title={server.enabled ? '当前会包含在下一次配置同步中' : '当前不会包含在下一次配置同步中'}
                  >
                    {server.enabled ? '参与同步' : '已排除'}
                  </button>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void toggleFavorite(server)}
                    className="rounded-md border border-gray-300 px-2.5 py-1.5 text-xs text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                    aria-label={favorites.has(server.server_id) ? `取消收藏 ${server.name}` : `收藏 ${server.name}`}
                  >
                    {favorites.has(server.server_id) ? '已收藏' : '收藏'}
                  </button>
                  <Link to={`/servers/${encodeURIComponent(server.server_id)}`} className="rounded-md border border-gray-300 px-2.5 py-1.5 text-xs text-gray-700 hover:bg-gray-50">
                    详情
                  </Link>
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void removeServer(server)}
                    className="rounded-md border border-red-200 px-2.5 py-1.5 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50"
                  >
                    移除
                  </button>
                </div>
              </div>
            </article>
          )
        })}
      </div>

      {filteredServers.length === 0 && (
        <div className="border border-gray-200 bg-white px-5 py-12 text-center">
          <p className="text-sm text-gray-600">
            {servers.length === 0 ? '你还没有追踪任何 Server。' : '当前筛选条件下没有 Server。'}
          </p>
          {servers.length === 0 && <Link to="/market" className="mt-3 inline-block text-sm font-medium text-blue-700 hover:underline">前往市场添加</Link>}
        </div>
      )}
    </div>
  )
}
