import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import {
  ApiRequestError,
  apiDelete,
  apiGet,
  apiPost,
  getAuthHeaders,
  getAuthState,
  uploadConfig,
} from '../api/client'

interface ConfigServer {
  name: string
  command?: string
  hub_id?: string
  hub_install_command?: string
  matched?: boolean
  enabled?: boolean
  agent?: string
  group_name?: string
}

export default function MyConfig() {
  const [servers, setServers] = useState<ConfigServer[]>([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [message, setMessage] = useState('')
  const [trackingStatus, setTrackingStatus] = useState<'idle' | 'uploaded' | 'cancelled'>('idle')
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const { token, userId } = getAuthState()

  const toPreviewServers = (result: any): ConfigServer[] => [
    ...(result.data?.matched || []).map((server: any) => ({
      name: server.hub_id || server.local_name,
      command: server.hub_install_command || server.local_command,
      hub_id: server.hub_id,
      matched: true,
    })),
    ...(result.data?.unmatched || []).map((server: any) => ({
      name: `@custom/${server.local_name}`,
      command: server.local_command,
      hub_id: `@custom/${server.local_name}`,
      matched: false,
    })),
  ]

  // 账户中的追踪记录是唯一权威来源；浏览器草稿不会替代账户数据。
  useEffect(() => {
    async function load() {
      if (!token || !userId) {
        setServers([])
        setMessage('请先登录后查看和管理自己的追踪配置')
        setLoading(false)
        return
      }
      try {
        const result = await apiGet<ConfigServer[]>('/config/user-servers')
        const currentServers = result.data || []
        setServers(currentServers)
        setTrackingStatus(currentServers.length > 0 ? 'uploaded' : 'idle')
      } catch (error) {
        setServers([])
        setMessage(
          error instanceof ApiRequestError && error.status === 401
            ? '登录状态已失效，请重新登录'
            : '加载追踪配置失败，请稍后重试'
        )
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [token, userId])

  const saveToServer = async (srvList: ConfigServer[]) => {
    const result: any = await apiPost('/config/user-servers/save', { servers: srvList })
    if (!result.success) {
      throw new Error(typeof result.error === 'string' ? result.error : '保存追踪配置失败')
    }
  }

  const removeServer = async (name: string) => {
    if (!window.confirm(`确定要移除 "${name}" 吗？`)) return
    const serverId = servers.find(server => server.name === name)?.hub_id || name
    try {
      await apiDelete(`/config/user-servers/${encodeURIComponent(serverId)}`)
      setServers(prev => prev.filter(s => (s.hub_id || s.name) !== serverId))
      setMessage(`已停止追踪 ${name}`)
    } catch {
      setMessage(`移除 ${name} 失败，请稍后重试`)
    }
    setTimeout(() => setMessage(''), 3000)
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!token || !userId) {
      setMessage('请先登录后检查配置')
      e.target.value = ''
      return
    }
    try {
      const result = await uploadConfig(file)
      if (result.success && result.data) {
        const previewServers = toPreviewServers(result)
        if (previewServers.length > 0) {
          setServers(previewServers)
          setPendingFile(file)
          setMessage(`已检测到 ${previewServers.length} 个可追踪 Server；确认后将以此文件替换当前追踪列表`)
          setTrackingStatus('idle')
        } else {
          setPendingFile(null)
          setMessage('配置中没有可追踪的 Server')
        }
      } else {
        setMessage(typeof result.error === 'string' ? result.error : '检查配置失败')
      }
    } catch {
      setMessage('检查配置失败，请确认文件为有效 JSON 后重试')
    }
    e.target.value = ''
    setTimeout(() => setMessage(''), 5000)
  }

  // 确认时才请求后端写入记录，并允许后端注册已发现或自定义的 Server。
  const handleUploadToHub = async () => {
    if (servers.length === 0) return
    if (!token || !userId) {
      setMessage('请先登录后开始追踪')
      return
    }
    try {
      if (pendingFile) {
        const result = await uploadConfig(pendingFile, '', true)
        if (!result.success) throw new Error(typeof result.error === 'string' ? result.error : '开始追踪失败')
        setServers(toPreviewServers(result))
        setPendingFile(null)
      } else {
        await saveToServer(servers)
      }
      setTrackingStatus('uploaded')
      setMessage('已保存到你的追踪列表。健康检查和已上报的调用数据可在监控页查看。')
    } catch (error) {
      setMessage(error instanceof Error ? error.message : '开始追踪失败，请稍后重试')
    }
    setTimeout(() => setMessage(''), 4000)
  }

  // 该操作会清空当前账户的个人追踪记录，不影响市场条目或其他用户。
  const handleCancelTracking = async () => {
    if (trackingStatus !== 'uploaded') {
      try {
        const result = await apiGet<ConfigServer[]>('/config/user-servers')
        const currentServers = result.data || []
        setServers(currentServers)
        setPendingFile(null)
        setTrackingStatus(currentServers.length > 0 ? 'uploaded' : 'cancelled')
        setMessage('已取消本次待确认的配置，原有追踪列表未修改')
      } catch {
        setMessage('取消待确认配置失败，请刷新后重试')
      }
      setTimeout(() => setMessage(''), 4000)
      return
    }

    if (!window.confirm('确定要停止追踪并清空当前账户的 Server 列表吗？Hub 将不再保留这些个人追踪记录。')) return
    try {
      await saveToServer([])
      setServers([])
      setPendingFile(null)
      setTrackingStatus('cancelled')
      setMessage('已停止追踪，个人追踪记录已从 Hub 中移除')
    } catch {
      setMessage('停止追踪失败，请稍后重试')
    }
    setTimeout(() => setMessage(''), 4000)
  }

  const handleDownload = async () => {
    if (servers.length === 0) return
    if (!token || !userId) {
      setMessage('请先登录后下载自己的配置')
      return
    }
    setDownloading(true)
    try {
      const res = await fetch('/api/v1/config/download?agent=generic', {
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error(`下载失败: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'mcp-hub-config.json'; a.click()
      URL.revokeObjectURL(url)
      setMessage('配置文件已下载')
    } catch (e) { setMessage('❌ 下载失败: ' + (e instanceof Error ? e.message : '')) }
    finally { setDownloading(false) }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="text-gray-400 text-lg">加载配置中...</div></div>
  }

  if (!token || !userId) {
    return (
      <div className="max-w-3xl mx-auto space-y-6">
        <h1 className="text-2xl font-bold text-gray-900">⚙️ 我的配置</h1>
        <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
          <p className="text-gray-700 font-medium">登录后检查、追踪和下载属于你自己的 MCP 配置</p>
          <Link to="/login" className="inline-block mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">登录</Link>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">⚙️ 我的配置</h1>
          <p className="text-sm text-gray-500 mt-1">检查本地 MCP 配置，确认后保存为你的 Hub 追踪列表</p>
        </div>
        <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">去市场添加 →</Link>
      </div>

      {/* Workflow Guide */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-5">
        <h2 className="font-semibold text-gray-900 mb-3">📋 操作流程</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">1</span>
            <p className="font-medium text-gray-800">上传配置</p>
            <p className="text-xs text-gray-500 mt-0.5">上传你本地的 MCP 配置文件，Hub 自动识别并匹配 Server</p>
          </div>
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">2</span>
            <p className="font-medium text-gray-800">确认追踪</p>
            <p className="text-xs text-gray-500 mt-0.5">确认后才会更新 Hub 中属于你的追踪列表</p>
          </div>
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">3</span>
            <p className="font-medium text-gray-800">下载配置</p>
            <p className="text-xs text-gray-500 mt-0.5">下载更新后的配置，替换本地文件，重启 Agent 即可生效</p>
          </div>
        </div>
        <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
          <p className="font-medium">💡 说明</p>
          <p>确认追踪只保存 Server 列表。调用次数、响应时长和 Token 数据需要已授权的本地网关或遥测设备主动上报；取消追踪不会删除市场条目或影响其他用户。</p>
        </div>
      </div>

      {/* Upload */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-2">📤 步骤 1：上传本地 MCP 配置</h2>
        <p className="text-sm text-gray-500 mb-3">
          上传 <code className="px-1 bg-gray-100 rounded text-xs">claude_desktop_config.json</code> 或 <code className="px-1 bg-gray-100 rounded text-xs">mcp.json</code>，Hub 自动识别并匹配市场中的 Server
        </p>
        <div className="flex gap-2">
          <label className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 cursor-pointer transition-colors">
            📁 选择文件
            <input type="file" accept=".json" onChange={handleUpload} className="hidden" />
          </label>
          <Link to="/config" className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors">
            完整配置中心 →
          </Link>
        </div>
      </div>

      {/* ── 上传/取消决策区 ── */}
      {servers.length > 0 && (
        <div className={`rounded-xl border-2 p-6 ${
          trackingStatus === 'uploaded' ? 'bg-green-50 border-green-300' :
          trackingStatus === 'cancelled' ? 'bg-gray-50 border-gray-300' :
          'bg-amber-50 border-amber-300'
        }`}>
          <h2 className="font-semibold text-gray-900 mb-2">⚡ 步骤 2：是否上传到 Hub 进行监控？</h2>

          {trackingStatus === 'uploaded' ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-600 text-white rounded-full text-sm font-medium">
                  ✅ 已保存到 Hub
                </span>
                <span className="text-sm text-green-700">你的 {servers.length} 个 MCP Server 已在个人追踪列表中</span>
              </div>
              <p className="text-sm text-green-700">
                已保存的 Server 可显示服务端状态和健康检查；本地调用数据仅在网关或遥测设备上报后出现。
              </p>
              <button
                onClick={handleCancelTracking}
                className="px-5 py-2 bg-white text-red-600 border border-red-300 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
              >
                ❌ 取消上传（停止追踪）
              </button>
            </div>
          ) : trackingStatus === 'cancelled' ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-gray-400 text-white rounded-full text-sm font-medium">
                  已取消上传
                </span>
                <span className="text-sm text-gray-500">Hub 不会追踪你的 MCP 配置和调用数据</span>
              </div>
              <p className="text-sm text-gray-500">
                已停止追踪。重新检查配置并确认后可再次建立追踪记录。
              </p>
              <button
                onClick={handleUploadToHub}
                className="px-5 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
              >
                ✅ 重新上传到 Hub
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-500 text-white rounded-full text-sm font-medium">
                  ⚠️ 待确认
                </span>
                <span className="text-sm text-amber-700">检测到 {servers.length} 个 MCP Server，请确认是否替换当前追踪列表</span>
              </div>
              <p className="text-sm text-amber-700">
                确认后，Hub 才会保存这份配置；此操作会替换当前账户的追踪 Server 列表。
              </p>
              <div className="flex gap-3">
                <button
                  onClick={handleUploadToHub}
                  className="px-6 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                >
                  ✅ 上传到 Hub
                </button>
                <button
                  onClick={handleCancelTracking}
                  className="px-6 py-2.5 bg-white text-gray-600 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
                >
                  ❌ 取消
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Server List */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">
            {trackingStatus === 'idle' ? '待确认的 Server' : '已追踪的 Server'} <span className="text-gray-400 font-normal">({servers.length})</span>
          </h2>
          <div className="flex gap-2">
            <button
              onClick={handleCancelTracking}
              className="text-xs text-red-500 hover:text-red-700"
            >
              停止追踪并清空
            </button>
          </div>
        </div>

        {message && (
          <div className={`mb-3 p-2 rounded text-sm ${
            message.startsWith('✅') ? 'bg-green-50 text-green-700' :
            message.startsWith('❌') ? 'bg-red-50 text-red-700' :
            'bg-blue-50 text-blue-700'
          }`}>{message}</div>
        )}

        {servers.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p>还没有添加任何 Server</p>
            <p className="text-sm mt-1">上传本地的配置文件，或去市场浏览添加</p>
            <Link to="/market" className="inline-block mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              去市场浏览
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {servers.map((s) => (
              <div key={s.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800 truncate">{s.name}</span>
                    {s.matched ? (
                      <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">已匹配</span>
                    ) : (
                      <span className="text-xs px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded">未匹配</span>
                    )}
                    <input
                      type="text"
                      defaultValue={s.group_name || ''}
                      placeholder="分组..."
                      onBlur={async (e) => {
                        const gname = e.target.value.trim()
                        if (!gname && !s.group_name) return
                        try {
                          const result: any = await apiPost('/config/groups/set', {
                            server_id: s.hub_id || s.name,
                            group_name: gname,
                          })
                          if (!result.success) throw new Error('保存失败')
                          setServers(prev => prev.map(server => (
                            (server.hub_id || server.name) === (s.hub_id || s.name)
                              ? { ...server, group_name: gname }
                              : server
                          )))
                          setMessage('分组已更新')
                          setTimeout(() => setMessage(''), 2000)
                        } catch { setMessage('分组保存失败') }
                      }}
                      className="px-1.5 py-0.5 text-xs border border-gray-200 rounded w-20 bg-white focus:ring-1 focus:ring-blue-400 outline-none"
                    />
                  </div>
                  <p className="text-xs text-gray-400 truncate mt-0.5 font-mono">{s.command || '—'}</p>
                </div>
                <button onClick={() => removeServer(s.name)}
                  className="ml-2 px-2 py-1 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                >删除</button>
              </div>
            ))}
          </div>
        )}

        {servers.length > 0 && (
          <div className="mt-4 space-y-3">
            <button onClick={handleDownload} disabled={downloading}
              className="w-full py-3 bg-gray-800 text-white rounded-xl hover:bg-gray-900 font-medium transition-colors disabled:opacity-50">
              {downloading ? '生成中...' : '📥 下载配置文件（用于替换本地 Agent 配置）'}
            </button>
            <p className="text-xs text-gray-400 text-center">
              下载结果只包含你当前追踪且可生成配置的 Server；替换本地 Agent 配置文件并重启后生效
            </p>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
              <p className="font-medium mb-1">当前追踪列表：</p>
              <ul className="list-disc list-inside space-y-0.5">
                {servers.map(s => (
                  <li key={s.name}>{s.name}</li>
                ))}
                <li className="text-blue-600">mcp-hub-gateway（需配置设备令牌后才会上报本地遥测）</li>
              </ul>
            </div>
          </div>
        )}

        {/* CLI Sync Command */}
        {servers.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-4 mt-4">
            <p className="text-sm font-medium text-gray-700 mb-2">🔄 一键同步到本地（CLI）</p>
            <p className="text-xs text-gray-500 mb-2">在你的本地机器上运行以下命令，自动下载配置并写入本地文件：</p>
            <div className="bg-gray-900 rounded-lg p-3 overflow-x-auto">
              <pre className="text-green-400 text-xs font-mono">
                {`mcp config sync --server ${window.location.origin}`}
              </pre>
            </div>
            <button onClick={() => {
              navigator.clipboard.writeText(`mcp config sync --server ${window.location.origin}`)
              setMessage('命令已复制到剪贴板')
              setTimeout(() => setMessage(''), 3000)
            }} className="mt-2 px-3 py-1.5 bg-gray-800 text-white rounded-lg text-xs hover:bg-gray-700 transition-colors">
              📋 复制命令
            </button>
            <p className="text-xs text-gray-400 mt-2">
              需要在本机安装 mcp-hub-cli 并先使用 mcp login 登录。同步会在覆盖前确认并创建带时间戳备份；随后可在监控页复制 mcp agent setup 命令启用本地监控。
            </p>
          </div>
        )}
      </div>

      {/* 配置草稿 */}
      <ConfigDrafts servers={servers} onLoad={(s) => {
        setServers(s)
        setPendingFile(null)
        setTrackingStatus('idle')
        setMessage('草稿已载入，确认后会替换当前追踪列表')
        setTimeout(() => setMessage(''), 2000)
      }} />
    </div>
  )
}

function ConfigDrafts({ servers, onLoad }: { servers: ConfigServer[], onLoad: (s: ConfigServer[]) => void }) {
  const [drafts, setDrafts] = useState<{ name: string; servers: ConfigServer[]; savedAt: string }[]>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_drafts') || '[]') } catch { return [] }
  })
  const [draftName, setDraftName] = useState('')

  const saveDraft = () => {
    if (!draftName.trim() || servers.length === 0) return
    const existing = drafts.filter(d => d.name !== draftName.trim())
    const updated = [...existing, { name: draftName.trim(), servers, savedAt: new Date().toISOString().slice(0, 16) }]
    setDrafts(updated)
    localStorage.setItem('mcp_hub_drafts', JSON.stringify(updated))
    setDraftName('')
  }

  const deleteDraft = (name: string) => {
    const updated = drafts.filter(d => d.name !== name)
    setDrafts(updated)
    localStorage.setItem('mcp_hub_drafts', JSON.stringify(updated))
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="font-semibold text-gray-900 mb-3">💾 配置草稿</h2>
      <p className="text-xs text-gray-500 mb-3">保存当前 Server 配置为草稿，方便在不同配置方案间快速切换</p>

      {/* 保存草稿 */}
      <div className="flex gap-2 mb-4">
        <input type="text" value={draftName} onChange={e => setDraftName(e.target.value)}
          placeholder="草稿名称（如：工作用/个人用）"
          className="flex-1 px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-1 focus:ring-blue-400 outline-none" />
        <button onClick={saveDraft} disabled={servers.length === 0 || !draftName.trim()}
          className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50">
          保存草稿
        </button>
      </div>

      {/* 草稿列表 */}
      {drafts.length === 0 ? (
        <p className="text-xs text-gray-400">暂存配置草稿，方便快速切换</p>
      ) : (
        <div className="space-y-1.5">
          {drafts.map(d => (
            <div key={d.name} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-xs">
              <div>
                <span className="font-medium text-gray-700">{d.name}</span>
                <span className="text-gray-400 ml-2">{d.servers.length} 个 Server</span>
                <span className="text-gray-300 ml-2">{d.savedAt}</span>
              </div>
              <div className="flex gap-1.5">
                <button onClick={() => { if (window.confirm(`加载草稿"${d.name}"将替换当前配置，确定？`)) onLoad(d.servers) }}
                  className="px-2 py-0.5 bg-green-100 text-green-700 rounded hover:bg-green-200">加载</button>
                <button onClick={() => { if (window.confirm('确定删除此草稿？')) deleteDraft(d.name) }}
                  className="px-2 py-0.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded">删除</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
