import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { getAuthHeaders, getAuthState, uploadConfig, downloadConfig } from '../api/client'
import InfoTooltip from '../components/InfoTooltip'
import { copyStatus, copyText } from '../utils/clipboard'

const AGENTS = [
  { id: 'claude-code', name: 'Claude Code', path: '~/.claude.json', extension: 'json', icon: '🤖' },
  { id: 'claude-desktop', name: 'Claude Desktop', path: 'Claude/claude_desktop_config.json', extension: 'json', icon: '🖥️' },
  { id: 'cursor', name: 'Cursor', path: '~/.cursor/mcp.json', extension: 'json', icon: '📝' },
  { id: 'vscode-copilot', name: 'VS Code Copilot', path: '.vscode/mcp.json', extension: 'json', icon: '💻' },
  { id: 'codex', name: 'Codex', path: '~/.codex/config.toml', extension: 'toml', icon: '🔧' },
  { id: 'trae', name: 'Trae', path: '~/.trae/mcp.json', extension: 'json', icon: '🚀' },
  { id: 'windsurf', name: 'Windsurf', path: '~/.codeium/windsurf/mcp_config.json', extension: 'json', icon: '🌊' },
  { id: 'generic', name: '通用 mcp.json', path: '~/.config/mcp-hub/mcp.json', extension: 'json', icon: '📄' },
]

type TrackingDecision = 'idle' | 'uploaded' | 'cancelled'

export default function ConfigPage() {
  const navigate = useNavigate()
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState('claude-code')
  const [downloading, setDownloading] = useState(false)
  const [message, setMessage] = useState('')
  const [previewData, setPreviewData] = useState<any>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [uploadResult, setUploadResult] = useState<any>(null)
  const [trackingDecision, setTrackingDecision] = useState<TrackingDecision>('idle')

  // Step 1: 选择文件 → 本地解析预览
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPendingFile(file)
    setMessage('')
    setUploadResult(null)
    setTrackingDecision('idle')
    try {
      const text = await file.text()
      const json = JSON.parse(text)
      const servers = json.mcpServers || {}
      const names = Object.keys(servers)
      if (names.length === 0) { setMessage('⚠️ 配置文件中未找到 mcpServers 定义'); setPendingFile(null); return }
      setPreviewData({ fileName: file.name, serverCount: names.length, servers: names })
    } catch {
      setMessage('❌ 文件格式无效，请上传 JSON 文件')
      setPreviewData(null)
      setPendingFile(null)
    }
  }

  // Step 2: 确认上传到服务器（匹配市场）
  const handleConfirmUpload = async () => {
    if (!pendingFile) return
    if (!getAuthState().token) {
      setMessage('❌ 请先登录后检查配置')
      return
    }
    setUploading(true)
    setMessage('')
    try {
      const r = await uploadConfig(pendingFile, selectedAgent)
      setUploadResult(r)
      setPreviewData(null)
      if (r.success) {
        setMessage(`✅ 检查完成！检测到 ${r.data?.server_count || 0} 个 Server，请确认是否追踪`)
        setTrackingDecision('idle')
      }
    } catch (err: any) {
      setUploadResult({ success: false, message: err.message || '上传失败' })
    } finally { setUploading(false) }
  }

  const handleCancelUpload = () => {
    setPreviewData(null)
    setPendingFile(null)
    setMessage('')
  }

  // Step 3: Only this confirmation request creates tracked Server records.
  const handleUploadToHub = async () => {
    if (!pendingFile) {
      setMessage('❌ 找不到待确认的配置文件，请重新检查')
      return
    }
    try {
      const result = await uploadConfig(pendingFile, selectedAgent, true)
      if (!result.success) throw new Error(result.message || '追踪配置失败')
      setUploadResult(result)
      setPendingFile(null)
      setTrackingDecision('uploaded')
      localStorage.setItem('mcp_hub_upload_result', JSON.stringify(result))
      setMessage('✅ 已保存到我的 Server。完成本地 Gateway 接入后，监控页会显示真实运行与调用数据。')
    } catch {
      setMessage('❌ 操作失败')
    }
    setTimeout(() => setMessage(''), 4000)
  }

  const handleCancelTracking = async () => {
    if (trackingDecision !== 'uploaded') {
      setTrackingDecision('cancelled')
      setPendingFile(null)
      setMessage('已取消，配置检查结果不会写入 Hub')
      return
    }
    // 从服务端清除所有已上传的 server 记录
    const allSids = [
      ...(uploadResult?.data?.matched?.map((m: any) => m.hub_id || m.local_name) || []),
      ...(uploadResult?.data?.unmatched?.map((u: any) => u.registered_id || u.local_name) || []),
    ]
    const serverIds = [...new Set(allSids.filter(Boolean))]
    if (serverIds.length > 0 && !window.confirm(
      `确定要取消追踪这 ${serverIds.length} 个 Server 吗？它们会从你的个人追踪列表中移除。`,
    )) return

    const failedIds: string[] = []
    for (const sid of serverIds) {
      try {
        const response = await fetch(`/api/v1/config/user-servers/${encodeURIComponent(sid)}`, {
          method: 'DELETE',
          headers: getAuthHeaders(),
        })
        if (!response.ok) failedIds.push(sid)
      } catch {
        failedIds.push(sid)
      }
    }
    if (failedIds.length > 0) {
      setMessage(`取消追踪未完成：${failedIds.length} 个 Server 未能移除，请稍后重试`)
      return
    }
    setTrackingDecision('cancelled')
    localStorage.removeItem('mcp_hub_upload_result')
    setMessage('已取消追踪，Hub 不再保留这批 Server 的个人追踪记录')
    setTimeout(() => setMessage(''), 4000)
  }

  const handleDownload = async () => {
    if (!getAuthState().token) {
      setMessage('❌ 请先登录后下载自己的配置')
      return
    }
    setDownloading(true)
    try {
      const res = await fetch(`/api/v1/config/download?agent=${selectedAgent}`, {
        headers: getAuthHeaders(),
      })
      if (!res.ok) throw new Error(`下载失败: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `mcp-hub-config-${selectedAgent}.${agent?.extension || 'json'}`
      a.click()
      URL.revokeObjectURL(url)
      setMessage('✅ 配置文件已下载')
    } catch { setMessage('❌ 下载失败') }
    finally { setDownloading(false) }
  }

  const agent = AGENTS.find(a => a.id === selectedAgent)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">⚙️ 配置中心</h1>
      <p className="text-gray-500 text-sm">选择配置文件 → 检查市场匹配 → 确认追踪 → 创建设备 → 接入本地 Gateway</p>

      {/* ── 步骤 1：上传配置 ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">📤 步骤 1：检查你的 MCP 配置</h2>
        <p className="text-sm text-gray-500 mb-4">
          上传你本地的 <code className="px-1 bg-gray-100 rounded text-xs">claude_desktop_config.json</code> 或 <code className="px-1 bg-gray-100 rounded text-xs">mcp.json</code>
        </p>

        {/* 文件选择区 */}
        {!previewData && (
          <label
            className={`block border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}`}
            onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) handleFileSelect({ target: { files: [f] } } as any) }}
          >
            <input type="file" accept=".json" onChange={handleFileSelect} className="hidden" />
            <div className="text-3xl mb-1">📂</div>
            <p className="text-gray-600 text-sm">拖拽 JSON 文件到此处，或点击选择</p>
          </label>
        )}

        {/* 预览 + 确认/取消 */}
        {previewData && !uploading && (
          <div className="p-4 bg-blue-50 rounded-lg border border-blue-200">
            <p className="text-sm font-medium text-blue-800 mb-2">
              📋 检测到 <strong>{previewData.serverCount}</strong> 个 MCP Server
            </p>
            <div className="flex flex-wrap gap-1 mb-3 max-h-40 overflow-y-auto">
              {previewData.servers.map((s: string) => (
                <span key={s} className="px-2 py-0.5 bg-white text-blue-600 rounded text-xs border border-blue-200">{s}</span>
              ))}
            </div>
            <p className="text-xs text-blue-600 mb-3">
              系统会检查这些 Server 是否在 Hub 市场中；检查本身不会保存追踪记录或修改 Server 状态
            </p>
            <div className="flex gap-2">
              <button onClick={handleConfirmUpload} className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
                ✅ 检查并匹配
              </button>
              <button onClick={handleCancelUpload} className="px-6 py-2 bg-white text-gray-600 border border-gray-300 rounded-lg text-sm hover:bg-gray-50">
                ❌ 取消
              </button>
            </div>
          </div>
        )}

        {uploading && (
          <div className="text-center py-6 text-gray-400">
            <p className="text-lg">⏳ 正在上传并匹配市场...</p>
          </div>
        )}

        {/* 匹配结果 */}
        {uploadResult && (
          <div className="mt-4 p-4 rounded-lg text-sm" style={{
            backgroundColor: uploadResult.success !== false ? '#EFF6FF' : '#FEF2F2',
            color: uploadResult.success !== false ? '#1D4ED8' : '#991B1B'
          }}>
            <p className="font-medium">{uploadResult.message || (uploadResult.success !== false ? '服务器匹配结果' : '上传失败')}</p>
            {uploadResult.data?.matched?.length > 0 && (
              <div className="mt-2 text-xs space-y-0.5">
                <p className="font-medium text-green-700">✅ Hub 已匹配 <strong>{uploadResult.data.matched.length}</strong> 个 Server：</p>
                {uploadResult.data.matched.map((m: any) => (
                  <p key={m.local_name} className="ml-2">• {m.local_name} → {m.hub_id}</p>
                ))}
              </div>
            )}
            {uploadResult.data?.unmatched?.length > 0 && (
              <div className="mt-2 text-xs space-y-0.5">
                <p className="font-medium text-yellow-700">⚠️ <strong>{uploadResult.data.unmatched.length}</strong> 个待作为自定义 Server 处理：</p>
                {uploadResult.data.unmatched.slice(0, 5).map((m: any) => (
                  <p key={m.local_name} className="ml-2">• {m.local_name}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── 步骤 2：确认追踪 ── */}
      {uploadResult && uploadResult.success !== false && (
        <div className={`rounded-xl border-2 p-6 ${
          trackingDecision === 'uploaded' ? 'bg-green-50 border-green-300' :
          trackingDecision === 'cancelled' ? 'bg-gray-50 border-gray-300' :
          'bg-amber-50 border-amber-300'
        }`}>
          <h2 className="font-semibold text-gray-900 mb-2">⚡ 步骤 2：是否保存到我的 Server？</h2>

          {trackingDecision === 'uploaded' ? (
            <div className="space-y-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-600 text-white rounded-full text-sm font-medium">✅ 已开始追踪</span>
              <p className="text-sm text-green-700">
                这些 Server 已保存到你的个人追踪列表。服务端状态、健康检查和已上报的调用统计可在监控页查看。
              </p>
              <button onClick={handleCancelTracking}
                className="px-4 py-1.5 bg-white text-red-600 border border-red-300 rounded-lg text-xs font-medium hover:bg-red-50">
                取消追踪
              </button>
            </div>
          ) : trackingDecision === 'cancelled' ? (
            <div className="space-y-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-gray-400 text-white rounded-full text-sm font-medium">未开始追踪</span>
              <p className="text-sm text-gray-500">本次检查结果没有保存。你可以重新选择同一文件进行检查。</p>
              <button onClick={handleUploadToHub}
                className="px-4 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700">
                ✅ 重新开始追踪
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-500 text-white rounded-full text-sm font-medium">⚠️ 待确认</span>
              <p className="text-sm text-amber-700">
                匹配完成。确认后会保存你的 Server 列表；本地调用数据需要通过已授权的遥测设备或网关主动上报。
              </p>
              <div className="flex gap-3 mt-3">
                <button onClick={handleUploadToHub}
                  className="px-6 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
                  ✅ 确认追踪
                </button>
                <button onClick={handleCancelTracking}
                  className="px-6 py-2.5 bg-white text-gray-600 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors">
                  ❌ 取消
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── 步骤 3：选择 Agent 工具 ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">🎯 步骤 3：选择你的 AI Agent</h2>
        <p className="text-sm text-gray-500 mb-4">
          选择你正在使用的 Agent。推荐继续执行步骤 4 接入 Gateway；下方原生配置仅用于不需要监控的直接连接。
        </p>
        <div className="flex gap-2 mb-4 flex-wrap">
          {AGENTS.map(a => (
            <button key={a.id} onClick={() => setSelectedAgent(a.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedAgent === a.id ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>
              {a.icon} {a.name}
            </button>
          ))}
        </div>

        {/* 导出不含监控的原生配置 */}
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-sm font-medium text-gray-700 mb-2">
            📥 导出「{agent?.name || 'Claude Code'}」原生直连配置
          </p>
          <p className="text-xs text-gray-500 mb-3">
            此文件会让 Agent 直接连接 Server，不经过 Gateway，因此不会产生 Hub 调用监控数据。合并到
            <code className="mx-1 px-1 bg-gray-200 rounded text-xs">{agent?.path || '~/.claude.json'}</code>
            前请先备份现有配置。
          </p>
          <button onClick={handleDownload} disabled={downloading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {downloading ? '⏳ 生成中...' : '📥 导出原生配置'}
          </button>
        </div>
      </div>

      {/* ── 步骤 4：启用监控 ── */}
      <div className="bg-white rounded-xl border border-green-200 bg-green-50 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">📊 步骤 4：接入本地 <InfoTooltip description="Gateway 在本机代理 Agent 与 MCP Server 的通信，并上报不含原始请求和响应内容的运行指标。">Gateway</InfoTooltip>（监控必需）</h2>
        <p className="text-sm text-gray-600 mb-4">
          追踪 Server 不会自动产生本地调用数据。请为每个使用的 Agent（如 Claude Code、Codex）在监控页分别创建设备，并将对应 <InfoTooltip description="设备令牌只用于本地 Gateway 上报指标，服务端会将它绑定到创建时选择的 Agent 类型。">设备令牌</InfoTooltip> 配置到本地 <InfoTooltip description="Gateway 是连接本地 Agent 与 MCP Server 的转发程序，负责在调用时采集最小化指标。">Gateway</InfoTooltip>；调用、延迟和 Token 统计才会上报且会按 Agent 隔离。
        </p>
        <div className="bg-gray-900 rounded-lg p-3 mb-3">
          <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap">
{`mcp-hub agent setup --agent ${selectedAgent} \\
  --hub-url ${window.location.origin} \\
  --telemetry-token mcpht_设备令牌`}
          </pre>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          请在监控页为当前 Agent 创建设备后使用“复制一键接入命令”。命令会先备份原配置，再迁移 stdio、Streamable HTTP 和 SSE Server。
        </p>
        <div className="flex gap-2">
          <button onClick={() => navigate('/monitor')}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
            创建设备并接入
          </button>
          <button onClick={() => navigate('/my-servers')}
            className="px-4 py-2 bg-white text-gray-700 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors">
            📦 我的 Server
          </button>
        </div>
      </div>

      {/* ── 本地诊断 ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-2">🔧 本地 Gateway 诊断</h2>
        <p className="mb-3 text-sm text-gray-500">在用户电脑执行，不会读取或修改 Hub 服务器上的 Agent 配置。</p>
        <div className="flex gap-2 flex-wrap">
          <button onClick={async () => {
            const copied = await copyText(`mcp-hub agent status --agent ${selectedAgent}`)
            setMessage(copyStatus(copied, '✅ 状态命令已复制'))
          }}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors">
          复制状态命令
          </button>
          <button onClick={async () => {
            const copied = await copyText(`mcp-hub agent doctor --agent ${selectedAgent}`)
            setMessage(copyStatus(copied, '✅ 自检命令已复制'))
          }}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors">
          复制自检命令
          </button>
          <button onClick={() => navigate('/local')}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors disabled:opacity-50">
          查看设备清单
          </button>
        </div>
      </div>

      {message && (
        <div className={`fixed bottom-4 right-4 p-3 rounded-lg text-sm shadow-lg z-50 ${
          message.startsWith('✅') ? 'bg-green-600 text-white' : message.startsWith('⚠️') ? 'bg-yellow-500 text-white' :
          message.startsWith('❌') ? 'bg-red-500 text-white' : 'bg-blue-600 text-white'
        }`}>
          {message}
          <button onClick={() => setMessage('')} className="ml-2 opacity-70 hover:opacity-100">✕</button>
        </div>
      )}
    </div>
  )
}
