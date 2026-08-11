import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, apiPost } from '../api/client'
import { copyStatus, copyText } from '../utils/clipboard'
import ConnectionStatusPanel, { type ConnectionStatusData } from './ConnectionStatusPanel'
import InfoTooltip from './InfoTooltip'

interface TelemetrySummary {
  days: number
  total_calls: number
  ok_calls: number
  error_calls: number
  success_rate: number
  avg_duration_ms: number
  input_tokens: number
  output_tokens: number
  total_tokens: number
  active_devices: number
  active_servers: number
  active_sessions: number
  p95_duration_ms: number
  current_queue_depth: number
  max_queue_depth: number
  input_bytes: number
  output_bytes: number
  total_bytes: number
  first_call_at: string | null
  last_call_at: string | null
  last_seen_at: string | null
}

interface TelemetryServer {
  server_id: string
  total_calls: number
  ok_calls: number
  error_calls: number
  success_rate: number
  avg_duration_ms: number
  total_tokens: number
  last_call_at: string | null
}

interface TelemetryDevice {
  id: string
  name: string
  agent_type: string
  gateway_version: string
  runtime_version: string
  platform: string
  architecture: string
  created_at: string | null
  last_seen_at: string | null
  gateway_last_seen_at: string | null
  revoked_at: string | null
}

interface TelemetryAgentSummary {
  agent_type: string
  total_calls: number
  ok_calls: number
  error_calls: number
  success_rate: number
  total_tokens: number
  device_count: number
  last_seen_at: string | null
}

interface CreatedDevice {
  device: TelemetryDevice
  token: string
}

interface TelemetryTool {
  server_id: string
  tool_name: string
  total_calls: number
  error_calls: number
  success_rate: number
  avg_duration_ms: number
  total_tokens: number
  total_bytes: number
  last_call_at: string | null
}

interface TelemetryPoint {
  date: string
  total_calls: number
  error_calls: number
  avg_duration_ms: number
  total_tokens: number
}

interface TelemetryResource {
  server_id: string
  sample_count: number
  avg_cpu_percent: number
  max_cpu_percent: number
  avg_memory_bytes: number
  max_memory_bytes: number
  process_uptime_seconds: number
  last_sample_at: string | null
}

interface TelemetryError {
  server_id: string
  error_code: string
  count: number
  last_seen_at: string | null
}

interface TelemetryOperation {
  operation: string
  total_calls: number
  error_calls: number
  avg_duration_ms: number
  last_call_at: string | null
}

interface TelemetryLifecycleEvent {
  server_id: string
  operation: string
  status: string
  duration_ms: number
  error_code: string
  server_version: string
  occurred_at: string
}

const AGENT_OPTIONS = [
  { id: 'claude-code', label: 'Claude Code' },
  { id: 'claude-desktop', label: 'Claude Desktop' },
  { id: 'codex', label: 'Codex' },
  { id: 'cursor', label: 'Cursor' },
  { id: 'windsurf', label: 'Windsurf' },
  { id: 'vscode-copilot', label: 'VS Code Copilot' },
  { id: 'trae', label: 'Trae' },
  { id: 'generic', label: '通用 MCP 客户端' },
] as const

const CLI_INSTALL_COMMAND = 'uv tool install --force "git+https://github.com/blankbrains/McpServerHub.git@main"'

function agentLabel(agentType: string): string {
  return AGENT_OPTIONS.find((agent) => agent.id === agentType)?.label || agentType
}

function formatTokens(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function formatDate(value: string | null): string {
  if (!value) return '-'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '-' : parsed.toLocaleString()
}

function formatBytes(value: number): string {
  if (value >= 1024 ** 3) return `${(value / 1024 ** 3).toFixed(1)} GB`
  if (value >= 1024 ** 2) return `${(value / 1024 ** 2).toFixed(1)} MB`
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${value} B`
}

function formatUptime(value: number): string {
  if (!value) return '-'
  const days = Math.floor(value / 86400)
  const hours = Math.floor((value % 86400) / 3600)
  return days > 0 ? `${days} 天 ${hours} 小时` : `${hours} 小时`
}

export default function TelemetryPanel() {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null)
  const [servers, setServers] = useState<TelemetryServer[]>([])
  const [devices, setDevices] = useState<TelemetryDevice[]>([])
  const [agents, setAgents] = useState<TelemetryAgentSummary[]>([])
  const [tools, setTools] = useState<TelemetryTool[]>([])
  const [points, setPoints] = useState<TelemetryPoint[]>([])
  const [resources, setResources] = useState<TelemetryResource[]>([])
  const [errors, setErrors] = useState<TelemetryError[]>([])
  const [operations, setOperations] = useState<TelemetryOperation[]>([])
  const [lifecycleEvents, setLifecycleEvents] = useState<TelemetryLifecycleEvent[]>([])
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatusData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deviceName, setDeviceName] = useState('Local MCP Agent')
  const [deviceAgentType, setDeviceAgentType] = useState('generic')
  const [selectedAgent, setSelectedAgent] = useState('')
  const [days, setDays] = useState(7)
  const [refreshVersion, setRefreshVersion] = useState(0)
  const [creating, setCreating] = useState(false)
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [createdDevice, setCreatedDevice] = useState<CreatedDevice | null>(null)
  const [copyState, setCopyState] = useState('')
  const hubUrl = window.location.origin
  const setupCommand = createdDevice
    ? [
        'mcp-hub agent setup',
        `--agent ${createdDevice.device.agent_type}`,
        `--hub-url ${hubUrl}`,
        `--telemetry-token ${createdDevice.token}`,
      ].join(' ')
    : ''
  const manualConfigCommand = createdDevice
    ? [
        'mcp-hub agent config',
        `--agent ${createdDevice.device.agent_type}`,
        `--hub-url ${hubUrl}`,
        `--telemetry-token ${createdDevice.token}`,
      ].join(' ')
    : ''

  useEffect(() => {
    let active = true
    const query = selectedAgent
      ? `&agent_type=${encodeURIComponent(selectedAgent)}`
      : ''

    const load = async () => {
      setLoading(true)
      setError('')
      try {
        const [
          connectionStatusResult,
          summaryResult,
          serversResult,
          devicesResult,
          agentsResult,
          toolsResult,
          timeseriesResult,
          resourcesResult,
          errorsResult,
          operationsResult,
          lifecycleResult,
        ] = await Promise.all([
          apiGet<ConnectionStatusData>('/telemetry/connection-status'),
          apiGet<TelemetrySummary>(`/telemetry/summary?days=${days}${query}`),
          apiGet<{ days: number; servers: TelemetryServer[] }>(`/telemetry/servers?days=${days}${query}`),
          apiGet<TelemetryDevice[]>('/telemetry/devices'),
          apiGet<{ days: number; agents: TelemetryAgentSummary[] }>(`/telemetry/agents?days=${days}`),
          apiGet<{ days: number; tools: TelemetryTool[] }>(`/telemetry/tools?days=${days}${query}`),
          apiGet<{ days: number; points: TelemetryPoint[] }>(`/telemetry/timeseries?days=${days}${query}`),
          apiGet<{ days: number; resources: TelemetryResource[] }>(`/telemetry/resources?days=${days}${query}`),
          apiGet<{ days: number; errors: TelemetryError[] }>(`/telemetry/errors?days=${days}${query}`),
          apiGet<{ days: number; operations: TelemetryOperation[] }>(`/telemetry/operations?days=${days}${query}`),
          apiGet<{ days: number; events: TelemetryLifecycleEvent[] }>(`/telemetry/lifecycle?days=${days}${query}`),
        ])
        if (!active) return
        setConnectionStatus(connectionStatusResult.data)
        setSummary(summaryResult.data)
        setServers(serversResult.data?.servers || [])
        setDevices(devicesResult.data || [])
        setAgents(agentsResult.data?.agents || [])
        setTools(toolsResult.data?.tools || [])
        setPoints(timeseriesResult.data?.points || [])
        setResources(resourcesResult.data?.resources || [])
        setErrors(errorsResult.data?.errors || [])
        setOperations(operationsResult.data?.operations || [])
        setLifecycleEvents(lifecycleResult.data?.events || [])
      } catch {
        if (active) setError('遥测数据加载失败，请稍后重试。')
      } finally {
        if (active) setLoading(false)
      }
    }

    void load()
    return () => {
      active = false
    }
  }, [days, refreshVersion, selectedAgent])

  const refresh = () => {
    setRefreshVersion((version) => version + 1)
  }

  const createDevice = async () => {
    const normalizedName = deviceName.trim()
    if (!normalizedName) {
      setError('请输入设备名称。')
      return
    }
    setCreating(true)
    setError('')
    try {
      const result = await apiPost<CreatedDevice>('/telemetry/devices', {
        name: normalizedName,
        agent_type: deviceAgentType,
      })
      if (!result.success || !result.data) throw new Error('Create device failed')
      setCreatedDevice(result.data)
      setDeviceName('Local MCP Agent')
      refresh()
    } catch {
      setError('设备密钥创建失败，请稍后重试。')
    } finally {
      setCreating(false)
    }
  }

  const revokeDevice = async (deviceId: string) => {
    if (!window.confirm('确定要撤销此设备令牌吗？使用该令牌的本地 Gateway 将无法继续上报，且无法恢复。')) return
    setRevokingId(deviceId)
    setError('')
    try {
      await apiPost(`/telemetry/devices/${encodeURIComponent(deviceId)}/revoke`)
      refresh()
    } catch {
      setError('设备撤销失败，请稍后重试。')
    } finally {
      setRevokingId(null)
    }
  }

  const copyToken = async () => {
    if (!createdDevice) return
    const copied = await copyText(createdDevice.token)
    setCopyState(copyStatus(copied, '设备密钥已复制'))
  }

  const copyConfig = async () => {
    if (!manualConfigCommand) return
    const copied = await copyText(manualConfigCommand)
    setCopyState(copyStatus(copied, '配置生成命令已复制'))
  }

  const copySetupCommand = async () => {
    if (!setupCommand) return
    const copied = await copyText(setupCommand)
    setCopyState(copyStatus(copied, '接入命令已复制'))
  }

  const registeredAgentTypes = new Set(agents.map((agent) => agent.agent_type))
  if (selectedAgent) registeredAgentTypes.add(selectedAgent)
  const visibleAgents = AGENT_OPTIONS.filter((agent) => registeredAgentTypes.has(agent.id))
  const maxTrendCalls = Math.max(...points.map((point) => point.total_calls), 1)

  return (
    <section className="space-y-4" aria-labelledby="telemetry-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="telemetry-heading" className="text-xl font-bold text-gray-900">本地 MCP 监控</h2>
          <p className="mt-1 text-sm text-gray-500">
            来自已授权本地 <InfoTooltip description="Gateway 是部署在本地 Agent 与 MCP Server 之间的转发程序，用于在不上传请求内容的前提下采集调用指标。">Gateway</InfoTooltip> 的真实调用、延迟、错误与 <InfoTooltip description="Token 是模型处理文本时使用的计量单位。这里是根据调用载荷估算的数量，不会上传原始提示词或响应内容。">估算载荷 Token</InfoTooltip>。
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={days}
            onChange={(event) => setDays(Number(event.target.value))}
            aria-label="监控时间范围"
            className="border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value={1}>最近 24 小时</option>
            <option value={7}>最近 7 天</option>
            <option value={30}>最近 30 天</option>
            <option value={90}>最近 90 天</option>
          </select>
          <button
            type="button"
            onClick={refresh}
            disabled={loading}
            className="border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {loading ? '刷新中...' : '刷新'}
          </button>
        </div>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <ConnectionStatusPanel data={connectionStatus} loading={loading} />

      <div className="border border-blue-200 bg-blue-50 px-4 py-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h3 className="font-semibold text-gray-900">首次接入：按顺序完成</h3>
            <p className="mt-1 text-sm text-gray-600">
              Hub 运行在服务器上，但 MCP Server 和 Gateway 必须运行在你的电脑上。只有经过本地 Gateway 的调用才会出现在这里。
            </p>
          </div>
          <Link to="/guide" className="text-sm font-medium text-blue-700 hover:text-blue-800">查看完整使用指南</Link>
        </div>
        <ol className="mt-4 grid gap-3 text-sm text-gray-700 md:grid-cols-2 xl:grid-cols-3">
          <li className="border-l-2 border-blue-500 pl-3">
            <p className="font-medium text-gray-900">1. 检查电脑能访问 Hub</p>
            <code className="mt-1 block break-all text-xs">curl {hubUrl}/api/v1/health</code>
          </li>
          <li className="border-l-2 border-blue-500 pl-3">
            <p className="font-medium text-gray-900">2. 安装本地 CLI</p>
            <code className="mt-1 block break-all text-xs">{CLI_INSTALL_COMMAND}</code>
            <p className="mt-1 text-xs text-gray-500">再运行 uv tool update-shell，重开终端后执行 mcp-hub --version。</p>
          </li>
          <li className="border-l-2 border-blue-500 pl-3">
            <p className="font-medium text-gray-900">3. 准备 Agent 配置</p>
            <p className="mt-1 text-xs text-gray-600">先确保 Codex、Claude Code 等 Agent 已经配置至少一个可用 MCP Server。</p>
          </li>
          <li className="border-l-2 border-blue-500 pl-3">
            <p className="font-medium text-gray-900">4. 创建独立设备</p>
            <p className="mt-1 text-xs text-gray-600">在右侧选择实际使用的 Agent 后创建设备。每个 Agent 使用一个独立令牌。</p>
          </li>
          <li className="border-l-2 border-blue-500 pl-3">
            <p className="font-medium text-gray-900">5. 执行接入并重启 Agent</p>
            <p className="mt-1 text-xs text-gray-600">运行生成的 agent setup 命令，核对预览并确认备份，然后完全退出并重新打开 Agent。</p>
          </li>
          <li className="border-l-2 border-blue-500 pl-3">
            <p className="font-medium text-gray-900">6. 产生真实调用并验证</p>
            <p className="mt-1 text-xs text-gray-600">让 Agent 实际调用一次 MCP 工具，再刷新本页；仅打开 Agent 或查看工具列表不会产生调用数据。</p>
          </li>
        </ol>
        <details className="mt-4 border-t border-blue-200 pt-3">
          <summary className="cursor-pointer text-sm font-medium text-gray-800">没有数据时如何排查</summary>
          <div className="mt-3 grid gap-3 text-xs text-gray-600 md:grid-cols-2">
            <div>
              <p className="font-medium text-gray-800">本地诊断命令</p>
              <pre className="mt-1 overflow-x-auto bg-white p-2 font-mono text-gray-700">{`mcp-hub agent status --agent codex
mcp-hub agent doctor --agent codex`}</pre>
            </div>
            <ul className="space-y-1">
              <li>确认 Agent 已完全重启，并且调用经过 mcp-hub Gateway；直接连接不会被监控。</li>
              <li>确认设备未撤销、Hub 地址可达，且本机防火墙或 VPN 没有阻止访问。</li>
              <li>离线事件会保存在本地 SQLite 队列中，网络恢复后自动重试。</li>
              <li>HTTP 页面若仍无法自动复制，可直接选中页面中的命令并按 Ctrl+C 或 Cmd+C。</li>
            </ul>
          </div>
        </details>
      </div>

      {loading && !summary ? (
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-500">正在加载遥测数据...</div>
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-8">
          {[
            ['调用次数', `过去 ${days} 天内由本地 Gateway 上报的工具调用总数。`, summary?.total_calls ?? 0, 'text-blue-700'],
            ['成功率', '状态为成功的调用占全部调用的比例。', `${summary?.success_rate ?? 0}%`, 'text-green-700'],
            ['估算载荷 Token', '按调用载荷估算的 Token 总量，不包含原始内容。', formatTokens(summary?.total_tokens ?? 0), 'text-violet-700'],
            ['平均延迟', '从 Gateway 发起调用到收到结果的平均耗时。', `${summary?.avg_duration_ms ?? 0}ms`, 'text-amber-700'],
            ['P95 延迟', '95% 的调用耗时不超过此值，用于识别长尾性能问题。', `${summary?.p95_duration_ms ?? 0}ms`, 'text-red-700'],
            ['传输数据', '仅统计序列化请求和响应的字节数，不保存内容。', formatBytes(summary?.total_bytes ?? 0), 'text-slate-700'],
            ['在线设备', '最近 3 分钟内成功连接 Hub 的未撤销本地 Agent 设备。', summary?.active_devices ?? 0, 'text-cyan-700'],
            ['待传队列', '本地最近一次事件上报时仍在离线队列中的事件数量。', summary?.current_queue_depth ?? 0, 'text-orange-700'],
          ].map(([label, description, value, color]) => (
            <div key={String(label)} className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-xs text-gray-500"><InfoTooltip description={String(description)}>{label}</InfoTooltip></p>
              <p className={`mt-1 text-xl font-semibold ${color}`}>{value}</p>
            </div>
          ))}
        </div>
      )}

      <div className="border border-gray-200 bg-white p-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h3 className="font-semibold text-gray-900">调用趋势</h3>
          <p className="text-xs text-gray-500">调用、错误与平均延迟按天聚合</p>
        </div>
        {points.length === 0 ? (
          <p className="py-8 text-center text-sm text-gray-500">当前时间范围内没有调用趋势。</p>
        ) : (
          <div className="overflow-x-auto">
            <div className="flex min-w-[560px] items-end gap-2 border-b border-gray-200 pb-2 pt-4">
              {points.map((point) => {
                const callHeight = Math.max(4, Math.round(point.total_calls / maxTrendCalls * 144))
                const errorHeight = point.total_calls
                  ? Math.round(point.error_calls / point.total_calls * callHeight)
                  : 0
                return (
                  <div key={point.date} className="flex min-w-12 flex-1 flex-col items-center">
                    <div className="mb-2 text-center text-[11px] text-gray-500">
                      <p>{point.total_calls} 次</p>
                      <p>{point.avg_duration_ms}ms</p>
                    </div>
                    <div className="relative w-7 bg-blue-500" style={{ height: `${callHeight}px` }} title={`${point.date}：${point.total_calls} 次调用，${point.error_calls} 次错误`}>
                      {errorHeight > 0 && <div className="absolute inset-x-0 bottom-0 bg-red-500" style={{ height: `${errorHeight}px` }} />}
                    </div>
                    <span className="mt-2 text-[10px] text-gray-400">{point.date.slice(5)}</span>
                  </div>
                )
              })}
            </div>
            <div className="mt-2 flex gap-4 text-xs text-gray-500">
              <span><span className="mr-1 inline-block h-2 w-2 bg-blue-500" />调用</span>
              <span><span className="mr-1 inline-block h-2 w-2 bg-red-500" />错误占比</span>
            </div>
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-2" role="group" aria-label="按 Agent 筛选遥测数据">
        <button
          type="button"
          onClick={() => setSelectedAgent('')}
          aria-pressed={selectedAgent === ''}
          className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
            selectedAgent === ''
              ? 'border-blue-600 bg-blue-600 text-white'
              : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
          }`}
        >
          全部
        </button>
        {visibleAgents.map((agent) => {
          const aggregate = agents.find((item) => item.agent_type === agent.id)
          return (
            <button
              key={agent.id}
              type="button"
              onClick={() => setSelectedAgent(agent.id)}
              aria-pressed={selectedAgent === agent.id}
              className={`rounded-md border px-3 py-1.5 text-sm transition-colors ${
                selectedAgent === agent.id
                  ? 'border-blue-600 bg-blue-600 text-white'
                  : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
              }`}
            >
              {agent.label}
              {aggregate ? ` · ${aggregate.total_calls} 次` : ''}
            </button>
          )
        })}
      </div>

      {agents.length > 0 && (
        <p className="text-xs text-gray-500">
          每个 Agent 使用独立设备令牌和本地队列。事件归属由服务端根据令牌绑定，客户端上报的身份不会被采信。
        </p>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-4 py-3">
            <h3 className="font-semibold text-gray-900">Server 调用情况</h3>
          </div>
          {servers.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-gray-500">尚未收到本地 Gateway 的调用数据。</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-left text-xs text-gray-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Server</th>
                    <th className="px-4 py-3 font-medium">调用</th>
                    <th className="px-4 py-3 font-medium"><InfoTooltip description="状态为成功的调用占该 Server 全部调用的比例。">成功率</InfoTooltip></th>
                    <th className="px-4 py-3 font-medium"><InfoTooltip description="该 Server 工具调用从发起到完成的平均耗时。">平均延迟</InfoTooltip></th>
                    <th className="px-4 py-3 font-medium"><InfoTooltip align="end" description="按调用载荷估算的 Token 总量，不包含原始请求或响应内容。">估算 Token</InfoTooltip></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {servers.map((server) => (
                    <tr key={server.server_id}>
                      <td className="max-w-[260px] truncate px-4 py-3 font-mono text-xs text-gray-700" title={server.server_id}>{server.server_id}</td>
                      <td className="px-4 py-3 text-gray-700">{server.total_calls}</td>
                      <td className={`px-4 py-3 ${server.success_rate >= 95 ? 'text-green-700' : 'text-red-700'}`}>{server.success_rate}%</td>
                      <td className="px-4 py-3 text-gray-700">{server.avg_duration_ms}ms</td>
                      <td className="px-4 py-3 text-gray-700">{formatTokens(server.total_tokens)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div id="telemetry-device-management" className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="font-semibold text-gray-900"><InfoTooltip description="设备是某个本地 Agent 的独立遥测身份。它的令牌只可用于上报指标，不能作为网页登录凭证。">本地 Agent 设备</InfoTooltip></h3>
          <p className="mt-1 text-xs text-gray-500">
            为每个使用的 Agent 分别创建 <InfoTooltip description="设备令牌将 Agent 类型绑定在服务端。上报事件无法自行声明或伪造归属。">设备令牌</InfoTooltip>，避免 Claude Code、Codex 等客户端的数据混在一起。
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto_auto]">
            <input
              value={deviceName}
              onChange={(event) => setDeviceName(event.target.value)}
              maxLength={100}
              aria-label="设备名称"
              className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
            <select
              value={deviceAgentType}
              onChange={(event) => setDeviceAgentType(event.target.value)}
              aria-label="Agent 类型"
              className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 outline-none focus:ring-2 focus:ring-blue-500"
            >
              {AGENT_OPTIONS.map((agent) => (
                <option key={agent.id} value={agent.id}>{agent.label}</option>
              ))}
            </select>
            <button
              type="button"
              onClick={() => void createDevice()}
              disabled={creating}
              className="rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {creating ? '创建中...' : '创建'}
            </button>
          </div>

          {createdDevice && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3">
              <p className="text-sm font-medium text-amber-900">设备密钥仅显示这一次</p>
              <p className="mt-1 text-xs text-amber-800">
                已绑定到 {agentLabel(createdDevice.device.agent_type)}，请只配置给这个 Agent。
              </p>
              <code className="mt-2 block break-all rounded bg-white p-2 text-xs text-gray-800">{createdDevice.token}</code>
              <p className="mt-3 text-xs font-medium text-amber-900">在本地终端执行以下完整命令</p>
              <pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap break-all rounded bg-gray-900 p-2 text-xs text-green-400" tabIndex={0}>
                {setupCommand}
              </pre>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => void copyToken()} className="rounded-md border border-amber-300 px-2 py-1 text-xs text-amber-900 hover:bg-amber-100">复制密钥</button>
                <button type="button" onClick={() => void copySetupCommand()} className="rounded-md border border-amber-300 px-2 py-1 text-xs text-amber-900 hover:bg-amber-100">复制一键接入命令</button>
                <button type="button" onClick={() => void copyConfig()} className="rounded-md border border-amber-300 px-2 py-1 text-xs text-amber-900 hover:bg-amber-100">复制配置生成命令</button>
                {copyState && <span className="self-center text-xs text-amber-900" role="status">{copyState}</span>}
              </div>
              <details className="mt-3">
                <summary className="cursor-pointer text-xs font-medium text-amber-900">高级备用：输出 Agent 对应格式的 Gateway 入口</summary>
                <p className="mt-2 text-xs text-amber-800">
                  此命令会按 Agent 输出 JSON 或 TOML 入口片段，但不会迁移现有 Server；首次接入仍应优先运行 agent setup。
                </p>
                <pre className="mt-2 max-h-52 overflow-auto whitespace-pre-wrap break-all rounded bg-white p-2 text-xs text-gray-700" tabIndex={0}>
                  {manualConfigCommand}
                </pre>
              </details>
            </div>
          )}

          <ul className="mt-4 divide-y divide-gray-100">
            {devices.length === 0 ? (
              <li className="py-4 text-sm text-gray-500">还没有已授权的本地 Agent。</li>
            ) : devices.map((device) => (
              <li key={device.id} className="flex items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-800">{device.name}</p>
                  <p className="text-xs text-gray-500">
                    {agentLabel(device.agent_type)} · 最近心跳 {formatDate(device.gateway_last_seen_at)}
                  </p>
                  {(device.gateway_version || device.runtime_version || device.platform) && (
                    <p className="mt-1 truncate text-[11px] text-gray-400" title={`${device.platform} ${device.architecture} · Python ${device.runtime_version} · Gateway ${device.gateway_version}`}>
                      {device.platform || 'unknown'} {device.architecture} · Python {device.runtime_version || '-'} · Gateway {device.gateway_version || '-'}
                    </p>
                  )}
                </div>
                {device.revoked_at ? (
                  <span className="text-xs text-gray-500">已撤销</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => void revokeDevice(device.id)}
                    disabled={revokingId === device.id}
                    className="rounded-md border border-red-200 px-2 py-1 text-xs text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {revokingId === device.id ? '撤销中...' : '撤销'}
                  </button>
                )}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <div className="overflow-hidden border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-4 py-3">
            <h3 className="font-semibold text-gray-900">工具调用</h3>
          </div>
          {tools.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-gray-500">当前时间范围内没有工具调用。</p>
          ) : (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-gray-50 text-left text-xs text-gray-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">工具</th>
                    <th className="px-4 py-3 font-medium">调用</th>
                    <th className="px-4 py-3 font-medium">成功率</th>
                    <th className="px-4 py-3 font-medium">平均延迟</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {tools.map((tool) => (
                    <tr key={`${tool.server_id}-${tool.tool_name}`}>
                      <td className="max-w-[260px] px-4 py-3">
                        <p className="truncate text-xs font-medium text-gray-800" title={tool.tool_name}>{tool.tool_name || '-'}</p>
                        <p className="truncate font-mono text-[11px] text-gray-400" title={tool.server_id}>{tool.server_id}</p>
                      </td>
                      <td className="px-4 py-3 text-gray-700">{tool.total_calls}</td>
                      <td className={`px-4 py-3 ${tool.success_rate >= 95 ? 'text-green-700' : 'text-red-700'}`}>{tool.success_rate}%</td>
                      <td className="px-4 py-3 text-gray-700">{tool.avg_duration_ms}ms</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="overflow-hidden border border-gray-200 bg-white">
          <div className="border-b border-gray-200 px-4 py-3">
            <h3 className="font-semibold text-gray-900">进程资源</h3>
          </div>
          {resources.length === 0 ? (
            <p className="px-4 py-8 text-center text-sm text-gray-500">尚未收到进程资源采样。</p>
          ) : (
            <div className="max-h-80 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-gray-50 text-left text-xs text-gray-500">
                  <tr>
                    <th className="px-4 py-3 font-medium">Server</th>
                    <th className="px-4 py-3 font-medium">CPU 平均/峰值</th>
                    <th className="px-4 py-3 font-medium">内存平均/峰值</th>
                    <th className="px-4 py-3 font-medium">运行时长</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {resources.map((resource) => (
                    <tr key={resource.server_id}>
                      <td className="max-w-[220px] truncate px-4 py-3 font-mono text-xs text-gray-700" title={resource.server_id}>{resource.server_id}</td>
                      <td className="px-4 py-3 text-xs text-gray-700">{resource.avg_cpu_percent}% / {resource.max_cpu_percent}%</td>
                      <td className="px-4 py-3 text-xs text-gray-700">{formatBytes(resource.avg_memory_bytes)} / {formatBytes(resource.max_memory_bytes)}</td>
                      <td className="px-4 py-3 text-xs text-gray-700">{formatUptime(resource.process_uptime_seconds)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      <div className="border border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h3 className="font-semibold text-gray-900">错误分类</h3>
          <span className="text-xs text-gray-500">不上传错误正文</span>
        </div>
        {errors.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-gray-500">当前时间范围内没有错误。</p>
        ) : (
          <ul className="divide-y divide-gray-100">
            {errors.map((item) => (
              <li key={`${item.server_id}-${item.error_code}`} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-gray-700" title={item.server_id}>{item.server_id || 'Gateway'}</span>
                <code className="bg-red-50 px-2 py-1 text-xs text-red-700">{item.error_code}</code>
                <span className="text-xs text-gray-600">{item.count} 次</span>
                <span className="text-xs text-gray-400">{formatDate(item.last_seen_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border border-gray-200 bg-white">
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h3 className="font-semibold text-gray-900">Server 生命周期</h3>
          <span className="text-xs text-gray-500">启动、停止、初始化失败与意外退出</span>
        </div>
        {lifecycleEvents.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-gray-500">当前时间范围内没有生命周期事件。</p>
        ) : (
          <ul className="max-h-80 divide-y divide-gray-100 overflow-auto">
            {lifecycleEvents.map((event, index) => (
              <li key={`${event.server_id}-${event.occurred_at}-${index}`} className="flex flex-wrap items-center gap-3 px-4 py-3 text-sm">
                <span className="min-w-0 flex-1 truncate font-mono text-xs text-gray-700" title={event.server_id}>{event.server_id || 'Gateway'}</span>
                <span className={`text-xs font-medium ${event.status === 'error' ? 'text-red-700' : event.status === 'ok' ? 'text-green-700' : 'text-amber-700'}`}>
                  {event.operation}
                </span>
                {event.duration_ms > 0 && <span className="text-xs text-gray-500">{event.duration_ms}ms</span>}
                {event.error_code && <code className="bg-red-50 px-2 py-1 text-xs text-red-700">{event.error_code}</code>}
                <span className="text-xs text-gray-400">{formatDate(event.occurred_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="border border-gray-200 bg-white">
        <div className="border-b border-gray-200 px-4 py-3">
          <h3 className="font-semibold text-gray-900">MCP 协议操作</h3>
        </div>
        {operations.length === 0 ? (
          <p className="px-4 py-6 text-center text-sm text-gray-500">当前时间范围内没有协议调用。</p>
        ) : (
          <div className="grid divide-y divide-gray-100 sm:grid-cols-2 sm:divide-x sm:divide-y-0 lg:grid-cols-4">
            {operations.map((operation) => (
              <div key={operation.operation} className="p-4">
                <p className="font-mono text-xs font-medium text-gray-800">{operation.operation}</p>
                <p className="mt-2 text-xl font-semibold text-gray-900">{operation.total_calls}</p>
                <p className="mt-1 text-xs text-gray-500">
                  错误 {operation.error_calls} · 平均 {operation.avg_duration_ms}ms
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
