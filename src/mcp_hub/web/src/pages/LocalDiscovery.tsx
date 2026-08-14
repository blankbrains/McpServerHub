import { useEffect, useState } from 'react'
import { apiGet } from '../api/client'
import AuthRequired from '../components/AuthRequired'
import InfoTooltip from '../components/InfoTooltip'
import { useAuthState } from '../hooks/useAuthState'

interface InventoryServer {
  server_name: string
  transport: string
  command_name: string
  env_keys: string[]
  header_keys: string[]
  config_hash: string
  server_version: string
  protocol_version: string
  capabilities: string[]
  tool_count: number
  running: boolean
  enabled: boolean
  configuration_error: string
  last_seen_at: string
  compatibility: {
    status: 'verified' | 'partial' | 'unsupported'
    reason_code: string
    reason: string
    features: {
      tools: boolean
      resources: boolean
      prompts: boolean
      tasks: boolean
    }
  }
}

interface InventoryDevice {
  id: string
  name: string
  agent_type: string
  gateway_version: string
  runtime_version: string
  platform: string
  architecture: string
  online: boolean
  server_count: number
  last_seen_at: string | null
  servers: InventoryServer[]
}

interface CompareItem {
  server_name: string
  present_in: string[]
  absent_in: string[]
  has_conflict: boolean
}

interface ConflictItem {
  server_name: string
  devices: Array<{
    device: string
    command_name: string
    env_keys: string[]
    config_hash: string
  }>
}

interface InventoryData {
  total_devices: number
  online_devices: number
  total_unique_servers: number
  devices: InventoryDevice[]
  compare: CompareItem[]
  conflicts: ConflictItem[]
}

function formatDate(value: string | null): string {
  if (!value) return '尚未连接'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '时间未知' : parsed.toLocaleString()
}

function compatibilityLabel(status: InventoryServer['compatibility']['status']): string {
  if (status === 'verified') return '协议已验证'
  if (status === 'partial') return '协议部分支持'
  return '协议不支持'
}

function compatibilityClass(status: InventoryServer['compatibility']['status']): string {
  if (status === 'verified') return 'border-green-200 bg-green-50 text-green-700'
  if (status === 'partial') return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-red-200 bg-red-50 text-red-700'
}

export default function LocalDiscovery() {
  const auth = useAuthState()
  const [data, setData] = useState<InventoryData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'devices' | 'compare' | 'conflicts'>('devices')
  const authenticated = Boolean(auth.token)

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const result = await apiGet<InventoryData>('/telemetry/inventory')
      setData(result.data)
    } catch {
      setError('本地清单加载失败，请检查登录状态或稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (authenticated) void load()
    else setLoading(false)
  }, [authenticated])

  if (!authenticated) {
    return (
      <AuthRequired
        title="登录后查看本地清单"
        description="本地清单仅来自你授权的 Agent 设备，并按账户隔离，登录后才能查看设备上报结果。"
      />
    )
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">本地清单</h1>
          <p className="mt-1 text-sm text-gray-500">
            仅展示已授权设备上报的脱敏清单，不会由服务器扫描浏览器所在电脑。
          </p>
        </div>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-60"
        >
          {loading ? '刷新中...' : '刷新'}
        </button>
      </div>

      {error && <div role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <div className="grid grid-cols-3 gap-3">
        {[
          ['已授权设备', data?.total_devices ?? 0, '设备令牌仍有效的本地 Agent 数量。'],
          ['在线设备', data?.online_devices ?? 0, '最近 3 分钟内与 Hub 通信的设备数量。'],
          ['唯一 Server', data?.total_unique_servers ?? 0, '所有设备当前清单中的去重 Server 数量。'],
        ].map(([label, value, description]) => (
          <div key={String(label)} className="border border-gray-200 bg-white p-4">
            <p className="text-xs text-gray-500"><InfoTooltip description={String(description)}>{label}</InfoTooltip></p>
            <p className="mt-1 text-2xl font-semibold text-gray-900">{value}</p>
          </div>
        ))}
      </div>

      <div className="flex w-fit border border-gray-200 bg-gray-50 p-1" role="tablist">
        {([
          ['devices', '设备清单'],
          ['compare', '跨 Agent 对比'],
          ['conflicts', `配置冲突${data?.conflicts.length ? ` (${data.conflicts.length})` : ''}`],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`px-3 py-2 text-sm ${tab === id ? 'bg-white font-medium text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-800'}`}
          >
            {label}
          </button>
        ))}
      </div>

      {loading && !data ? (
        <div className="border border-gray-200 bg-white px-4 py-10 text-center text-sm text-gray-500">正在读取设备清单...</div>
      ) : tab === 'devices' ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {(data?.devices || []).map((device) => (
            <section key={device.id} className="border border-gray-200 bg-white">
              <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
                <div>
                  <h2 className="font-semibold text-gray-900">{device.name}</h2>
                  <p className="text-xs text-gray-500">{device.agent_type} · {formatDate(device.last_seen_at)}</p>
                  {(device.gateway_version || device.runtime_version || device.platform) && (
                    <p className="mt-1 text-[11px] text-gray-400">
                      {device.platform || 'unknown'} {device.architecture} · Python {device.runtime_version || '-'} · Gateway {device.gateway_version || '-'}
                    </p>
                  )}
                </div>
                <span className={`text-xs font-medium ${device.online ? 'text-green-700' : 'text-gray-500'}`}>
                  {device.online ? '在线' : '离线'}
                </span>
              </div>
              {device.servers.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-gray-500">该设备尚未上报 Server 清单。</p>
              ) : (
                <ul className="divide-y divide-gray-100">
                  {device.servers.map((server) => (
                    <li key={server.server_name} className="px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-gray-800">{server.server_name}</p>
                          <p className="mt-0.5 text-xs text-gray-500">
                            {server.command_name || server.transport}
                            {server.server_version ? ` · v${server.server_version}` : ''}
                            {server.protocol_version ? ` · MCP ${server.protocol_version}` : ''}
                            {server.tool_count > 0 ? ` · ${server.tool_count} 个工具` : ''}
                            {server.env_keys.length > 0 ? ` · 环境变量 ${server.env_keys.join(', ')}` : ''}
                            {server.header_keys.length > 0 ? ` · 请求头 ${server.header_keys.join(', ')}` : ''}
                          </p>
                          {server.capabilities.length > 0 && (
                            <p className="mt-1 text-[11px] text-gray-400">
                              能力：{server.capabilities.join('、')}
                            </p>
                          )}
                          <p className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-gray-500">
                            <span
                              className={`border px-1.5 py-0.5 ${compatibilityClass(server.compatibility.status)}`}
                              title={server.compatibility.reason}
                            >
                              {compatibilityLabel(server.compatibility.status)}
                            </span>
                            <span>
                              工具 {server.compatibility.features.tools ? '支持' : '未声明'} ·
                              资源 {server.compatibility.features.resources ? '支持' : '未声明'} ·
                              提示词 {server.compatibility.features.prompts ? '支持' : '未声明'} ·
                              任务 {server.compatibility.features.tasks ? '支持' : '暂不支持'}
                            </span>
                          </p>
                        </div>
                        <span className={`text-xs ${server.running ? 'text-green-700' : server.enabled ? 'text-amber-700' : 'text-gray-500'}`}>
                          {server.configuration_error ? server.configuration_error : server.running ? '运行中' : server.enabled ? '未运行' : '已禁用'}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          ))}
          {(data?.devices.length || 0) === 0 && (
            <div className="border border-gray-200 bg-white px-5 py-10 text-center text-sm text-gray-500 lg:col-span-2">
              尚无设备清单。请先在监控页创建设备并完成本地 Gateway 配置。
            </div>
          )}
        </div>
      ) : tab === 'compare' ? (
        <div className="overflow-hidden border border-gray-200 bg-white">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left text-xs text-gray-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Server</th>
                  <th className="px-4 py-3 font-medium">存在于</th>
                  <th className="px-4 py-3 font-medium">缺失于</th>
                  <th className="px-4 py-3 font-medium">配置</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(data?.compare || []).map((item) => (
                  <tr key={item.server_name}>
                    <td className="px-4 py-3 font-medium text-gray-900">{item.server_name}</td>
                    <td className="px-4 py-3 text-xs text-gray-600">{item.present_in.join('、') || '-'}</td>
                    <td className="px-4 py-3 text-xs text-gray-600">{item.absent_in.join('、') || '-'}</td>
                    <td className={`px-4 py-3 text-xs ${item.has_conflict ? 'text-amber-700' : 'text-green-700'}`}>
                      {item.has_conflict ? '不一致' : '一致'}
                    </td>
                  </tr>
                ))}
                {(data?.compare.length || 0) === 0 && (
                  <tr><td colSpan={4} className="px-4 py-10 text-center text-gray-500">暂无可对比的清单。</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          {(data?.conflicts || []).map((conflict) => (
            <section key={conflict.server_name} className="border border-amber-200 bg-white p-4">
              <h2 className="font-semibold text-gray-900">{conflict.server_name}</h2>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                {conflict.devices.map((device) => (
                  <div key={`${conflict.server_name}-${device.device}`} className="bg-gray-50 p-3 text-xs">
                    <p className="font-medium text-gray-700">{device.device}</p>
                    <p className="mt-1 text-gray-500">命令：{device.command_name || '-'}</p>
                    <p className="text-gray-500">环境变量：{device.env_keys.join(', ') || '无'}</p>
                    <p className="mt-1 font-mono text-gray-400">配置指纹 {device.config_hash.slice(0, 12)}</p>
                  </div>
                ))}
              </div>
            </section>
          ))}
          {(data?.conflicts.length || 0) === 0 && (
            <div className="border border-gray-200 bg-white px-4 py-10 text-center text-sm text-gray-500">当前未发现跨设备配置冲突。</div>
          )}
        </div>
      )}
    </div>
  )
}
