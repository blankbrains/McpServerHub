import { useEffect, useState } from 'react'
import { apiGet, apiPost } from '../api/client'

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
  created_at: string | null
  last_seen_at: string | null
  revoked_at: string | null
}

interface CreatedDevice {
  device: TelemetryDevice
  token: string
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

async function copyText(value: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(value)
    return true
  } catch {
    return false
  }
}

export default function TelemetryPanel() {
  const [summary, setSummary] = useState<TelemetrySummary | null>(null)
  const [servers, setServers] = useState<TelemetryServer[]>([])
  const [devices, setDevices] = useState<TelemetryDevice[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [deviceName, setDeviceName] = useState('Local MCP Agent')
  const [creating, setCreating] = useState(false)
  const [revokingId, setRevokingId] = useState<string | null>(null)
  const [createdDevice, setCreatedDevice] = useState<CreatedDevice | null>(null)
  const [copyState, setCopyState] = useState('')

  const load = async () => {
    setError('')
    try {
      const [summaryResult, serversResult, devicesResult] = await Promise.all([
        apiGet<TelemetrySummary>('/telemetry/summary?days=7'),
        apiGet<{ days: number; servers: TelemetryServer[] }>('/telemetry/servers?days=7'),
        apiGet<TelemetryDevice[]>('/telemetry/devices'),
      ])
      setSummary(summaryResult.data)
      setServers(serversResult.data?.servers || [])
      setDevices(devicesResult.data || [])
    } catch {
      setError('遥测数据加载失败，请稍后重试。')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
  }, [])

  const createDevice = async () => {
    const normalizedName = deviceName.trim()
    if (!normalizedName) {
      setError('请输入设备名称。')
      return
    }
    setCreating(true)
    setError('')
    try {
      const result = await apiPost<CreatedDevice>('/telemetry/devices', { name: normalizedName })
      if (!result.success || !result.data) throw new Error('Create device failed')
      setCreatedDevice(result.data)
      setDeviceName('Local MCP Agent')
      await load()
    } catch {
      setError('设备密钥创建失败，请稍后重试。')
    } finally {
      setCreating(false)
    }
  }

  const revokeDevice = async (deviceId: string) => {
    setRevokingId(deviceId)
    setError('')
    try {
      await apiPost(`/telemetry/devices/${encodeURIComponent(deviceId)}/revoke`)
      await load()
    } catch {
      setError('设备撤销失败，请稍后重试。')
    } finally {
      setRevokingId(null)
    }
  }

  const copyToken = async () => {
    if (!createdDevice) return
    const copied = await copyText(createdDevice.token)
    setCopyState(copied ? '已复制' : '复制失败')
  }

  const copyConfig = async () => {
    if (!createdDevice) return
    const config = {
      mcpServers: {
        'mcp-hub': {
          command: 'mcp',
          args: ['serve'],
          env: {
            MCP_HUB_REPORT_URL: window.location.origin,
            MCP_HUB_TELEMETRY_TOKEN: createdDevice.token,
          },
        },
      },
    }
    const copied = await copyText(JSON.stringify(config, null, 2))
    setCopyState(copied ? '配置已复制' : '复制失败')
  }

  return (
    <section className="space-y-4" aria-labelledby="telemetry-heading">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 id="telemetry-heading" className="text-xl font-bold text-gray-900">本地 MCP 监控</h2>
          <p className="mt-1 text-sm text-gray-500">来自已授权本地 Gateway 的真实调用、延迟、错误与估算载荷 Token。</p>
        </div>
        <button
          type="button"
          onClick={() => { setLoading(true); void load() }}
          disabled={loading}
          className="rounded-lg border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? '刷新中...' : '刷新'}
        </button>
      </div>

      {error && (
        <div role="alert" className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      {loading && !summary ? (
        <div className="rounded-lg border border-gray-200 bg-white px-4 py-8 text-center text-sm text-gray-500">正在加载遥测数据...</div>
      ) : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          {[
            ['调用次数', summary?.total_calls ?? 0, 'text-blue-700'],
            ['成功率', `${summary?.success_rate ?? 0}%`, 'text-green-700'],
            ['估算载荷 Token', formatTokens(summary?.total_tokens ?? 0), 'text-violet-700'],
            ['平均延迟', `${summary?.avg_duration_ms ?? 0}ms`, 'text-amber-700'],
            ['活跃设备', summary?.active_devices ?? 0, 'text-slate-700'],
          ].map(([label, value, color]) => (
            <div key={String(label)} className="rounded-lg border border-gray-200 bg-white p-4">
              <p className="text-xs text-gray-500">{label}</p>
              <p className={`mt-1 text-xl font-semibold ${color}`}>{value}</p>
            </div>
          ))}
        </div>
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
                    <th className="px-4 py-3 font-medium">成功率</th>
                    <th className="px-4 py-3 font-medium">平均延迟</th>
                    <th className="px-4 py-3 font-medium">估算 Token</th>
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

        <div className="rounded-lg border border-gray-200 bg-white p-4">
          <h3 className="font-semibold text-gray-900">本地 Agent 设备</h3>
          <div className="mt-3 flex gap-2">
            <input
              value={deviceName}
              onChange={(event) => setDeviceName(event.target.value)}
              maxLength={100}
              aria-label="设备名称"
              className="min-w-0 flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500"
            />
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
              <code className="mt-2 block break-all rounded bg-white p-2 text-xs text-gray-800">{createdDevice.token}</code>
              <div className="mt-2 flex flex-wrap gap-2">
                <button type="button" onClick={() => void copyToken()} className="rounded-md border border-amber-300 px-2 py-1 text-xs text-amber-900 hover:bg-amber-100">复制密钥</button>
                <button type="button" onClick={() => void copyConfig()} className="rounded-md border border-amber-300 px-2 py-1 text-xs text-amber-900 hover:bg-amber-100">复制 Gateway 配置</button>
                {copyState && <span className="self-center text-xs text-amber-900" role="status">{copyState}</span>}
              </div>
            </div>
          )}

          <ul className="mt-4 divide-y divide-gray-100">
            {devices.length === 0 ? (
              <li className="py-4 text-sm text-gray-500">还没有已授权的本地 Agent。</li>
            ) : devices.map((device) => (
              <li key={device.id} className="flex items-center gap-3 py-3">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-gray-800">{device.name}</p>
                  <p className="text-xs text-gray-500">最后在线 {formatDate(device.last_seen_at)}</p>
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
    </section>
  )
}
