import { useState } from 'react'
import { Link } from 'react-router-dom'
import { copyStatus, copyText } from '../utils/clipboard'

export interface ConnectionStatusDevice {
  id: string
  name: string
  agent_type: string
  state:
    | 'waiting_configuration'
    | 'waiting_restart'
    | 'gateway_online'
    | 'connected'
    | 'data_backlog'
    | 'partial_connection'
    | 'offline'
    | 'revoked'
  label: string
  reason: string
  next_action: string
  next_action_code: string
  gateway_version: string
  runtime_version: string
  platform: string
  architecture: string
  setup_completed_at: string | null
  gateway_first_seen_at: string | null
  gateway_last_seen_at: string | null
  first_call_at: string | null
  last_event_at: string | null
  queue_depth: number
  server_count: number
  configuration_error_count: number
  last_error_code: string
  revoked_at: string | null
}

export interface ConnectionStatusData {
  total_devices: number
  online_devices: number
  connected_devices: number
  attention_devices: number
  devices: ConnectionStatusDevice[]
}

interface ConnectionStatusPanelProps {
  data: ConnectionStatusData | null
  loading: boolean
}

const AGENT_LABELS: Record<string, string> = {
  'claude-code': 'Claude Code',
  'claude-desktop': 'Claude Desktop',
  codex: 'Codex',
  cursor: 'Cursor',
  windsurf: 'Windsurf',
  'vscode-copilot': 'VS Code Copilot',
  trae: 'Trae',
  generic: '通用 MCP 客户端',
}

const STATE_STYLES: Record<ConnectionStatusDevice['state'], string> = {
  waiting_configuration: 'border-gray-300 bg-gray-50 text-gray-700',
  waiting_restart: 'border-amber-300 bg-amber-50 text-amber-800',
  gateway_online: 'border-cyan-300 bg-cyan-50 text-cyan-800',
  connected: 'border-green-300 bg-green-50 text-green-800',
  data_backlog: 'border-orange-300 bg-orange-50 text-orange-800',
  partial_connection: 'border-yellow-300 bg-yellow-50 text-yellow-800',
  offline: 'border-red-300 bg-red-50 text-red-800',
  revoked: 'border-gray-300 bg-gray-100 text-gray-600',
}

function formatDate(value: string | null): string {
  if (!value) return '尚无'
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '尚无' : parsed.toLocaleString()
}

function agentLabel(agentType: string): string {
  return AGENT_LABELS[agentType] || agentType
}

export default function ConnectionStatusPanel({
  data,
  loading,
}: ConnectionStatusPanelProps) {
  const [copyMessage, setCopyMessage] = useState('')

  const copyDoctorCommand = async (agentType: string) => {
    const copied = await copyText(`mcp-hub agent doctor --agent ${agentType}`)
    setCopyMessage(copyStatus(copied, '诊断命令已复制'))
  }

  return (
    <section className="border border-gray-200 bg-white" aria-labelledby="connection-status-heading">
      <header className="flex flex-wrap items-start justify-between gap-3 border-b border-gray-200 px-4 py-4">
        <div>
          <h3 id="connection-status-heading" className="text-base font-semibold text-gray-900">
            接入状态
          </h3>
          <p className="mt-1 text-sm text-gray-500">
            以 Gateway 心跳和真实工具调用为准，配置扫描不会被误判为在线。
          </p>
        </div>
        {data && data.total_devices > 0 && (
          <dl className="flex gap-5 text-right">
            <div>
              <dt className="text-xs text-gray-500">在线</dt>
              <dd className="text-lg font-semibold text-green-700">{data.online_devices}</dd>
            </div>
            <div>
              <dt className="text-xs text-gray-500">需处理</dt>
              <dd className="text-lg font-semibold text-amber-700">{data.attention_devices}</dd>
            </div>
          </dl>
        )}
      </header>

      {loading && !data ? (
        <div className="px-4 py-8 text-center text-sm text-gray-500" role="status">
          正在确认本地 Gateway 接入状态...
        </div>
      ) : !data || data.devices.length === 0 ? (
        <div className="px-4 py-7">
          <p className="font-medium text-gray-900">尚未创建本地 Agent 设备</p>
          <p className="mt-1 text-sm text-gray-500">
            先创建设备并执行生成的接入命令，面板随后会显示配置、在线和首次调用阶段。
          </p>
          <a
            href="#telemetry-device-management"
            className="mt-3 inline-flex text-sm font-medium text-blue-700 hover:text-blue-800"
          >
            前往设备管理
          </a>
        </div>
      ) : (
        <div className="divide-y divide-gray-200">
          {data.devices.map((device) => {
            const canRunDoctor = [
              'partial_connection',
              'offline',
              'data_backlog',
            ].includes(device.state)
            return (
              <article key={device.id} className="px-4 py-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h4 className="truncate font-semibold text-gray-900">{device.name}</h4>
                      <span
                        className={`rounded-md border px-2 py-0.5 text-xs font-medium ${STATE_STYLES[device.state]}`}
                      >
                        {device.label}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-600">
                      {agentLabel(device.agent_type)} · {device.reason}
                    </p>
                    {(device.gateway_version || device.platform) && (
                      <p className="mt-1 text-xs text-gray-400">
                        Gateway {device.gateway_version || '-'} · {device.platform || 'unknown'} {device.architecture} · Python {device.runtime_version || '-'}
                      </p>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-sm">
                    {canRunDoctor && (
                      <button
                        type="button"
                        onClick={() => void copyDoctorCommand(device.agent_type)}
                        className="border border-gray-300 px-3 py-1.5 font-medium text-gray-700 hover:bg-gray-50"
                      >
                        复制诊断命令
                      </button>
                    )}
                    {device.state === 'partial_connection' && (
                      <Link to="/local" className="font-medium text-blue-700 hover:text-blue-800">
                        查看本地清单
                      </Link>
                    )}
                    {device.state === 'revoked' && (
                      <a href="#telemetry-device-management" className="font-medium text-blue-700 hover:text-blue-800">
                        创建新设备
                      </a>
                    )}
                  </div>
                </div>

                <dl className="mt-4 grid grid-cols-2 gap-x-5 gap-y-3 sm:grid-cols-3 xl:grid-cols-6">
                  <div>
                    <dt className="text-xs text-gray-500">最近心跳</dt>
                    <dd className="mt-1 text-sm font-medium text-gray-800">
                      {formatDate(device.gateway_last_seen_at)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">已迁移 Server</dt>
                    <dd className="mt-1 text-sm font-medium text-gray-800">{device.server_count}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">配置错误</dt>
                    <dd className={`mt-1 text-sm font-medium ${device.configuration_error_count > 0 ? 'text-red-700' : 'text-gray-800'}`}>
                      {device.configuration_error_count}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">首次调用</dt>
                    <dd className="mt-1 text-sm font-medium text-gray-800">
                      {formatDate(device.first_call_at)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">待上传队列</dt>
                    <dd className={`mt-1 text-sm font-medium ${device.queue_depth > 0 ? 'text-orange-700' : 'text-gray-800'}`}>
                      {device.queue_depth}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-xs text-gray-500">配置完成</dt>
                    <dd className="mt-1 text-sm font-medium text-gray-800">
                      {formatDate(device.setup_completed_at)}
                    </dd>
                  </div>
                </dl>

                <div className="mt-4 border-l-2 border-blue-500 bg-blue-50 px-3 py-2">
                  <p className="text-xs font-medium text-blue-900">下一步</p>
                  <p className="mt-0.5 text-sm text-blue-800">{device.next_action}</p>
                </div>
              </article>
            )
          })}
        </div>
      )}

      {copyMessage && (
        <p className="border-t border-gray-200 px-4 py-2 text-xs text-gray-600" role="status">
          {copyMessage}
        </p>
      )}
    </section>
  )
}
