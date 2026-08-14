import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  ApiRequestError,
  apiDelete,
  apiGet,
  apiPost,
  favoriteServer,
  getFavoriteServers,
} from '../api/client'
import AuthRequired from '../components/AuthRequired'
import InfoTooltip from '../components/InfoTooltip'
import { useAuthState } from '../hooks/useAuthState'

type TabId = 'all' | 'discovered' | 'tracked' | 'connected' | 'attention' | 'conflicts'

interface OverviewDevice {
  device_id: string
  device_name: string
  agent_type: string
  online: boolean
  running: boolean
  enabled: boolean
  config_hash: string
  configuration_error: string
  last_seen_at: string
}

interface PrimaryAction {
  code: 'compare_configuration' | 'diagnose' | 'track' | 'view_setup' | 'view_monitoring'
  label: string
  type: 'api' | 'link'
  target: string
}

interface OverviewServer {
  entity_id: string
  server_id: string
  name: string
  description: string
  market_status: 'listed' | 'unlisted'
  market_id: string | null
  tracking_status: 'tracked' | 'untracked'
  tracked: boolean
  matched: boolean
  enabled: boolean
  local_names: string[]
  discovered: boolean
  gateway_status: 'connected' | 'direct_retained' | 'configuration_error' | 'not_connected'
  runtime_status: 'running' | 'stopped' | 'offline' | 'unknown'
  call_status: 'called' | 'no_calls'
  config_status: 'consistent' | 'conflict' | 'unknown'
  security_status: 'verified' | 'unreviewed' | 'blocked'
  device_count: number
  online_device_count: number
  devices: OverviewDevice[]
  call_count_7d: number
  token_consumption: number
  success_rate: number
  last_call_at: string | null
  needs_attention: boolean
  primary_action: PrimaryAction
}

interface OverviewData {
  days: number
  summary: {
    total: number
    discovered: number
    tracked: number
    connected: number
    needs_attention: number
    conflicts: number
  }
  servers: OverviewServer[]
}

const EMPTY_SUMMARY: OverviewData['summary'] = {
  total: 0,
  discovered: 0,
  tracked: 0,
  connected: 0,
  needs_attention: 0,
  conflicts: 0,
}

const GATEWAY_LABELS: Record<OverviewServer['gateway_status'], string> = {
  connected: '已接入 Gateway',
  direct_retained: '保留直连',
  configuration_error: '配置错误',
  not_connected: '未接入 Gateway',
}

const RUNTIME_LABELS: Record<OverviewServer['runtime_status'], string> = {
  running: '运行中',
  stopped: '已停止',
  offline: '设备离线',
  unknown: '运行未知',
}

function fmtNum(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function badgeClass(kind: string): string {
  if (['connected', 'running', 'verified', 'listed', 'tracked', 'called', 'consistent'].includes(kind)) {
    return 'border-green-200 bg-green-50 text-green-800'
  }
  if (['conflict', 'configuration_error', 'blocked'].includes(kind)) {
    return 'border-red-200 bg-red-50 text-red-800'
  }
  if (['direct_retained', 'offline', 'stopped'].includes(kind)) {
    return 'border-amber-200 bg-amber-50 text-amber-800'
  }
  return 'border-gray-200 bg-gray-50 text-gray-600'
}

function StateBadge({ kind, label }: { kind: string; label: string }) {
  return (
    <span className={`inline-flex whitespace-nowrap rounded-md border px-2 py-0.5 text-xs ${badgeClass(kind)}`}>
      {label}
    </span>
  )
}

export default function MyServers() {
  const auth = useAuthState()
  const [data, setData] = useState<OverviewData | null>(null)
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
    if (!auth.token) {
      setData({ days: 7, summary: EMPTY_SUMMARY, servers: [] })
      setFavorites(new Set())
      setSelected(new Set())
      setError('')
      setNotice('')
      setLoading(false)
      return
    }

    if (refresh) setRefreshing(true)
    setError('')
    try {
      const [overviewResult, favoriteResult] = await Promise.all([
        apiGet<OverviewData>('/my-mcp/overview?days=7'),
        getFavoriteServers().catch(() => ({ success: true, data: [] })),
      ])
      setData(overviewResult.data || { days: 7, summary: EMPTY_SUMMARY, servers: [] })
      setFavorites(new Set((favoriteResult.data || []).map(server => server.id)))
    } catch (loadError) {
      setData({ days: 7, summary: EMPTY_SUMMARY, servers: [] })
      setError(
        loadError instanceof ApiRequestError && loadError.status === 401
          ? '登录状态已失效，请重新登录。'
          : 'MCP 状态加载失败，请稍后重试。'
      )
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    void load()
  }, [auth.token])

  const servers = data?.servers || []
  const summary = data?.summary || EMPTY_SUMMARY
  const filteredServers = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase()
    return servers.filter(server => {
      if (tab === 'discovered' && !server.discovered) return false
      if (tab === 'tracked' && !server.tracked) return false
      if (tab === 'connected' && server.gateway_status !== 'connected') return false
      if (tab === 'attention' && !server.needs_attention) return false
      if (tab === 'conflicts' && server.config_status !== 'conflict') return false
      if (!normalizedQuery) return true
      return `${server.name} ${server.server_id} ${server.local_names.join(' ')} ${server.description}`
        .toLowerCase()
        .includes(normalizedQuery)
    })
  }, [query, servers, tab])

  const selectedEligible = filteredServers.filter(server => server.tracked)

  const withAction = async (entityId: string, action: () => Promise<void>) => {
    setActing(previous => new Set(previous).add(entityId))
    setError('')
    setNotice('')
    try {
      await action()
    } finally {
      setActing(previous => {
        const next = new Set(previous)
        next.delete(entityId)
        return next
      })
    }
  }

  const trackServer = async (server: OverviewServer) => {
    await withAction(server.entity_id, async () => {
      try {
        const result = await apiPost('/my-mcp/track', { server_id: server.server_id })
        if (!result.success) throw new Error('track rejected')
        setNotice(`${server.name} 已加入当前账户追踪列表。`)
        await load(true)
      } catch {
        setError(`加入追踪 ${server.name} 失败。`)
      }
    })
  }

  const toggleEnabled = async (server: OverviewServer) => {
    await withAction(server.entity_id, async () => {
      try {
        const enabled = !server.enabled
        const result = await apiPost('/config/user-servers/toggle', {
          server_id: server.server_id,
          enabled,
        })
        if (!result.success) throw new Error('toggle rejected')
        setData(previous => previous ? {
          ...previous,
          servers: previous.servers.map(item => (
            item.entity_id === server.entity_id ? { ...item, enabled } : item
          )),
        } : previous)
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

  const toggleFavorite = async (server: OverviewServer) => {
    if (!server.market_id) return
    await withAction(server.entity_id, async () => {
      try {
        const result = await favoriteServer(server.market_id as string)
        setFavorites(previous => {
          const next = new Set(previous)
          if (result.favorited) next.add(server.market_id as string)
          else next.delete(server.market_id as string)
          return next
        })
      } catch {
        setError(`更新 ${server.name} 的收藏状态失败。`)
      }
    })
  }

  const removeServer = async (server: OverviewServer) => {
    if (!window.confirm(
      `确定从当前账户追踪列表移除“${server.name}”吗？本地配置、市场条目和遥测历史不会被删除。`
    )) return

    await withAction(server.entity_id, async () => {
      try {
        await apiDelete(`/config/user-servers/${encodeURIComponent(server.server_id)}`)
        setSelected(previous => {
          const next = new Set(previous)
          next.delete(server.entity_id)
          return next
        })
        setNotice(`${server.name} 已从追踪列表移除。`)
        await load(true)
      } catch {
        setError(`移除 ${server.name} 失败。`)
      }
    })
  }

  const toggleSelected = (entityId: string) => {
    setSelected(previous => {
      const next = new Set(previous)
      if (next.has(entityId)) next.delete(entityId)
      else next.add(entityId)
      return next
    })
  }

  const toggleSelectAll = () => {
    const visibleIds = selectedEligible.map(server => server.entity_id)
    setSelected(previous => (
      visibleIds.length > 0 && visibleIds.every(entityId => previous.has(entityId))
        ? new Set()
        : new Set(visibleIds)
    ))
  }

  const batchUpdate = async (action: 'enable' | 'disable' | 'remove') => {
    const selectedServers = servers.filter(server => selected.has(server.entity_id) && server.tracked)
    if (selectedServers.length === 0) return
    if (
      action === 'remove'
      && !window.confirm(`确定移除选中的 ${selectedServers.length} 个追踪 Server 吗？`)
    ) return

    setBatchActing(true)
    setError('')
    let failed = 0
    for (const server of selectedServers) {
      try {
        if (action === 'remove') {
          await apiDelete(`/config/user-servers/${encodeURIComponent(server.server_id)}`)
        } else {
          await apiPost('/config/user-servers/toggle', {
            server_id: server.server_id,
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
    if (failed > 0) setError(`${failed}/${selectedServers.length} 个操作失败。`)
    else setNotice(`已完成 ${selectedServers.length} 个 Server 的批量操作。`)
  }

  if (!auth.token) {
    return (
      <AuthRequired
        title="登录后管理我的 MCP"
        description="追踪列表、Gateway 状态、配置冲突和真实调用都属于当前账户，登录后才能查看和操作。"
      />
    )
  }

  if (loading) {
    return <div className="py-16 text-center text-sm text-gray-500">正在聚合你的 MCP 状态...</div>
  }

  const tabs: Array<[TabId, string, number]> = [
    ['all', '全部', summary.total],
    ['discovered', '本地已发现', summary.discovered],
    ['tracked', '已追踪', summary.tracked],
    ['connected', '已接入', summary.connected],
    ['attention', '需要处理', summary.needs_attention],
    ['conflicts', '多设备冲突', summary.conflicts],
  ]

  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">我的 MCP</h1>
          <p className="mt-1 text-sm text-gray-500">
            {summary.discovered} 个本地已发现，{summary.tracked} 个已追踪，{summary.connected} 个已接入。
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
          <Link to="/market" className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700">
            发现更多
          </Link>
        </div>
      </header>

      <div className="border-l-4 border-blue-500 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        市场收录、账户追踪、Gateway 接入、运行和调用是独立状态。未收录的本地 Server 只在你的账户中可见，加入追踪不会自动发布到市场。
      </div>

      {error && <div role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}
      {notice && <div role="status" className="border border-green-200 bg-green-50 px-4 py-3 text-sm text-green-700">{notice}</div>}

      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-3">
        <div className="flex max-w-full overflow-x-auto border border-gray-200 bg-gray-50 p-1" role="tablist">
          {tabs.map(([id, label, count]) => (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={tab === id}
              onClick={() => {
                setTab(id)
                setSelected(new Set())
              }}
              className={`whitespace-nowrap px-3 py-1.5 text-sm ${tab === id ? 'bg-white font-medium text-gray-900 shadow-sm' : 'text-gray-600 hover:text-gray-900'}`}
            >
              {label} {count}
            </button>
          ))}
        </div>
        <input
          value={query}
          onChange={event => setQuery(event.target.value)}
          placeholder="搜索名称、市场 ID 或本地名称"
          aria-label="搜索我的 MCP"
          className="w-full max-w-sm rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
        />
      </div>

      {selected.size > 0 && (
        <div className="flex flex-wrap items-center gap-2 border border-blue-200 bg-blue-50 px-3 py-2">
          <span className="text-sm font-medium text-blue-800">已选 {selected.size} 个追踪 Server</span>
          <button type="button" disabled={batchActing} onClick={() => void batchUpdate('enable')} className="rounded-md border border-blue-300 px-2 py-1 text-xs text-blue-800 hover:bg-blue-100 disabled:opacity-50">加入同步</button>
          <button type="button" disabled={batchActing} onClick={() => void batchUpdate('disable')} className="rounded-md border border-blue-300 px-2 py-1 text-xs text-blue-800 hover:bg-blue-100 disabled:opacity-50">排除同步</button>
          <button type="button" disabled={batchActing} onClick={() => void batchUpdate('remove')} className="rounded-md border border-red-300 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:opacity-50">移除追踪</button>
        </div>
      )}

      {selectedEligible.length > 0 && (
        <label className="flex w-fit items-center gap-2 text-xs text-gray-500">
          <input
            type="checkbox"
            checked={selectedEligible.every(server => selected.has(server.entity_id))}
            onChange={toggleSelectAll}
          />
          选择当前列表中的追踪 Server
        </label>
      )}

      <div className="divide-y divide-gray-200 border border-gray-200 bg-white">
        {filteredServers.map(server => {
          const busy = acting.has(server.entity_id)
          const favorite = Boolean(server.market_id && favorites.has(server.market_id))
          return (
            <article key={server.entity_id} className="p-4">
              <div className="flex flex-wrap items-start gap-3">
                <div className="h-5 w-4 flex-shrink-0">
                  {server.tracked && (
                    <input
                      type="checkbox"
                      checked={selected.has(server.entity_id)}
                      onChange={() => toggleSelected(server.entity_id)}
                      aria-label={`选择 ${server.name}`}
                    />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {server.market_id ? (
                      <Link to={`/servers/${encodeURIComponent(server.market_id)}`} className="font-semibold text-gray-900 hover:text-blue-700">
                        {server.name}
                      </Link>
                    ) : (
                      <h2 className="font-semibold text-gray-900">{server.name}</h2>
                    )}
                    <StateBadge kind={server.market_status} label={server.market_status === 'listed' ? '市场已收录' : '本地私有'} />
                    <StateBadge kind={server.tracking_status} label={server.tracked ? '已追踪' : '未追踪'} />
                    <StateBadge kind={server.gateway_status} label={GATEWAY_LABELS[server.gateway_status]} />
                    <StateBadge kind={server.runtime_status} label={RUNTIME_LABELS[server.runtime_status]} />
                    <StateBadge kind={server.call_status} label={server.call_status === 'called' ? '有真实调用' : '暂无调用'} />
                    <StateBadge
                      kind={server.config_status}
                      label={
                        server.config_status === 'conflict'
                          ? '配置冲突'
                          : server.config_status === 'consistent'
                          ? '配置一致'
                          : '配置未知'
                      }
                    />
                    <StateBadge
                      kind={server.security_status}
                      label={
                        server.security_status === 'blocked'
                          ? '安全已阻止'
                          : server.security_status === 'verified'
                          ? '安全已验证'
                          : '安全未审查'
                      }
                    />
                  </div>
                  <p className="mt-1 truncate text-xs text-gray-500">
                    {server.market_id || server.local_names.join(', ') || server.server_id}
                  </p>
                  {server.description && <p className="mt-2 line-clamp-2 text-sm text-gray-600">{server.description}</p>}
                  <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500">
                    <InfoTooltip description="当前用户设备在过去 7 天真实上报的工具调用次数。">
                      <span>调用 {fmtNum(server.call_count_7d)}</span>
                    </InfoTooltip>
                    <InfoTooltip description="根据 MCP 调用载荷估算，不等同于模型供应商账单 Token。">
                      <span>估算 Token {fmtNum(server.token_consumption)}</span>
                    </InfoTooltip>
                    <span>成功率 {server.success_rate}%</span>
                    <span>{server.online_device_count}/{server.device_count} 设备在线</span>
                    {server.tracked && <span>{server.enabled ? '参与下次同步' : '已排除同步'}</span>}
                  </div>
                </div>

                <div className="flex items-start gap-2">
                  {server.primary_action.code === 'track' ? (
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void trackServer(server)}
                      className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
                    >
                      {busy ? '处理中...' : server.primary_action.label}
                    </button>
                  ) : (
                    <Link
                      to={server.primary_action.target}
                      className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white hover:bg-blue-700"
                    >
                      {server.primary_action.label}
                    </Link>
                  )}

                  {server.tracked && (
                    <details className="relative">
                      <summary className="cursor-pointer list-none rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50">
                        更多
                      </summary>
                      <div className="absolute right-0 z-20 mt-1 w-44 border border-gray-200 bg-white p-1 shadow-lg">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void toggleEnabled(server)}
                          className="block w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                        >
                          {server.enabled ? '排除下次同步' : '加入下次同步'}
                        </button>
                        {server.market_id && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => void toggleFavorite(server)}
                            className="block w-full px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50"
                          >
                            {favorite ? '取消收藏' : '收藏'}
                          </button>
                        )}
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => void removeServer(server)}
                          className="block w-full px-3 py-2 text-left text-sm text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          移除追踪
                        </button>
                      </div>
                    </details>
                  )}
                </div>
              </div>
            </article>
          )
        })}

        {filteredServers.length === 0 && (
          <div className="px-5 py-12 text-center">
            <p className="text-sm text-gray-600">
              {servers.length === 0 ? '尚未发现或追踪任何 MCP Server。' : '当前筛选条件下没有 Server。'}
            </p>
            {servers.length === 0 && (
              <Link to="/guide" className="mt-3 inline-block text-sm font-medium text-blue-700 hover:underline">
                查看本地接入步骤
              </Link>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
