import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadConfig, downloadConfig } from '../api/client'

const AGENTS = [
  { id: 'claude-code', name: 'Claude Code', path: '~/.config/Claude/claude_desktop_config.json', icon: '🤖' },
  { id: 'cursor', name: 'Cursor', path: '~/.cursor/mcp.json', icon: '📝' },
  { id: 'codex', name: 'Codex', path: '~/.codex/mcp.json', icon: '🔧' },
  { id: 'trae', name: 'Trae', path: '~/.trae/mcp.json', icon: '🚀' },
  { id: 'generic', name: '通用 mcp.json', path: '~/.config/mcp-hub/mcp.json', icon: '📄' },
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
    setUploading(true)
    setMessage('')
    try {
      const r = await uploadConfig(pendingFile, selectedAgent)
      setUploadResult(r)
      setPreviewData(null)
      setPendingFile(null)
      if (r.success) {
        setMessage(`✅ 上传成功！检测到 ${r.data?.server_count || 0} 个 Server，请选择是否上传到 Hub 进行监控`)
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

  // Step 3: 用户决定是否上传到 Hub
  // 注意：upload_config 已经在后端将全部 Server（含 matched + unmatched）写入 user_servers
  // 这里只是确认决策状态，不需要再重写
  const handleUploadToHub = async () => {
    try {
      setTrackingDecision('uploaded')
      localStorage.setItem('mcp_hub_upload_result', JSON.stringify(uploadResult))
      setMessage('✅ 已上传到 Hub！你的 MCP Server 将受到持续监控')
    } catch {
      setMessage('❌ 操作失败')
    }
    setTimeout(() => setMessage(''), 4000)
  }

  const handleCancelTracking = async () => {
    // 从服务端清除所有已上传的 server 记录
    const userId = localStorage.getItem('mcp_hub_user') || 'anonymous'
    const allSids = [
      ...(uploadResult?.data?.matched?.map((m: any) => m.hub_id || m.local_name) || []),
      ...(uploadResult?.data?.unmatched?.map((u: any) => u.local_name) || []),
    ]
    for (const sid of allSids) {
      try {
        await fetch(`/api/v1/config/user-servers/${encodeURIComponent(sid)}`, {
          method: 'DELETE',
          headers: { 'x-user-id': userId },
        })
      } catch {}
    }
    setTrackingDecision('cancelled')
    localStorage.removeItem('mcp_hub_upload_result')
    setMessage('已取消上传，Hub 不会追踪你的 MCP 配置')
    setTimeout(() => setMessage(''), 4000)
  }

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const userId = localStorage.getItem('mcp_hub_user') || 'anonymous'
      const res = await fetch(`/api/v1/config/download?agent=${selectedAgent}`, {
        headers: { 'x-user-id': userId },
      })
      if (!res.ok) throw new Error(`下载失败: ${res.status}`)
      const blob = await res.blob()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `mcp-hub-config-${selectedAgent}.json`
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
      <p className="text-gray-500 text-sm">上传你的 MCP 配置文件 → 检查匹配 → 决定是否上传到 Hub → 选择 Agent → 启用监控</p>

      {/* ── 步骤 1：上传配置 ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">📤 步骤 1：上传你的 MCP 配置</h2>
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
              系统将检查这些 Server 是否在 Hub 市场中，并展示匹配结果
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
                <p className="font-medium text-yellow-700">⚠️ <strong>{uploadResult.data.unmatched.length}</strong> 个已注册为自定义：</p>
                {uploadResult.data.unmatched.slice(0, 5).map((m: any) => (
                  <p key={m.local_name} className="ml-2">• {m.local_name}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── 步骤 2：决定是否上传到 Hub ── */}
      {uploadResult && uploadResult.success !== false && (
        <div className={`rounded-xl border-2 p-6 ${
          trackingDecision === 'uploaded' ? 'bg-green-50 border-green-300' :
          trackingDecision === 'cancelled' ? 'bg-gray-50 border-gray-300' :
          'bg-amber-50 border-amber-300'
        }`}>
          <h2 className="font-semibold text-gray-900 mb-2">⚡ 步骤 2：是否上传到 Hub 进行监控？</h2>

          {trackingDecision === 'uploaded' ? (
            <div className="space-y-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-600 text-white rounded-full text-sm font-medium">✅ 已上传到 Hub</span>
              <p className="text-sm text-green-700">
                你的 MCP Server 配置已上传到 Hub。当你的 Agent 通过 Hub 网关调用 MCP 时，调用数据将自动记录到监控大屏。
              </p>
              <button onClick={handleCancelTracking}
                className="px-4 py-1.5 bg-white text-red-600 border border-red-300 rounded-lg text-xs font-medium hover:bg-red-50">
                撤销上传
              </button>
            </div>
          ) : trackingDecision === 'cancelled' ? (
            <div className="space-y-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-gray-400 text-white rounded-full text-sm font-medium">已取消上传</span>
              <p className="text-sm text-gray-500">Hub 不会追踪你的 MCP 配置和调用数据。你可以随时重新上传。</p>
              <button onClick={handleUploadToHub}
                className="px-4 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700">
                ✅ 重新上传到 Hub
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-500 text-white rounded-full text-sm font-medium">⚠️ 待确认</span>
              <p className="text-sm text-amber-700">
                匹配完成。请选择是否将你的 Server 配置上传到 Hub。上传后，Hub 将记录你的 Server 信息并持续监控调用数据。
              </p>
              <div className="flex gap-3 mt-3">
                <button onClick={handleUploadToHub}
                  className="px-6 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
                  ✅ 上传到 Hub
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
        <h2 className="font-semibold text-gray-900 mb-1">🎯 步骤 3：选择你的 AI Agent 工具</h2>
        <p className="text-sm text-gray-500 mb-4">
          选择你正在使用的 AI Agent 工具。Hub 会根据你选择的 Agent 生成对应的配置文件格式，确保 MCP 调用能被正确路由和监控。
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

        {/* 下载配置文件 */}
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-sm font-medium text-gray-700 mb-2">
            📥 下载「{agent?.name || 'Claude Code'}」格式的配置文件
          </p>
          <p className="text-xs text-gray-500 mb-3">
            下载后替换到 <code className="px-1 bg-gray-200 rounded text-xs">{agent?.path || '~/.config/Claude/claude_desktop_config.json'}</code>，重启 Agent 即可生效
          </p>
          <button onClick={handleDownload} disabled={downloading}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {downloading ? '⏳ 生成中...' : `📥 下载配置文件`}
          </button>
        </div>
      </div>

      {/* ── 步骤 4：启用监控 ── */}
      <div className="bg-white rounded-xl border border-green-200 bg-green-50 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">📊 步骤 4：启用调用监控</h2>
        <p className="text-sm text-gray-600 mb-4">
          要将 Agent 中的 MCP 调用数据上报到 Hub，需要在你的本地 Agent 配置文件中添加 Hub 网关。
          网关会透明代理所有 MCP 调用，并自动将调用次数、响应时长等数据记录到 Hub 监控大屏。
        </p>
        <div className="bg-gray-900 rounded-lg p-3 mb-3">
          <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap">
{`"mcp-hub-gateway": {
  "command": "mcp",
  "args": ["serve"]
}`}
          </pre>
        </div>
        <p className="text-xs text-gray-500 mb-3">
          添加后，所有 MCP 工具调用都会经过 Hub 网关，数据自动记录到监控大屏
        </p>
        <div className="flex gap-2">
          <button onClick={() => { navigator.clipboard.writeText('"mcp-hub-gateway": {\n  "command": "mcp",\n  "args": ["serve"]\n}'); setMessage('✅ 已复制到剪贴板') }}
            className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
            📋 复制配置
          </button>
          <button onClick={() => navigate('/monitor')}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors">
            📈 查看监控大屏
          </button>
          <button onClick={() => navigate('/my-servers')}
            className="px-4 py-2 bg-white text-gray-700 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors">
            📦 我的 Server
          </button>
        </div>
      </div>

      {/* ── 高级功能 ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-3">🔧 高级功能</h2>
        <div className="flex gap-2 flex-wrap">
          <button onClick={async () => {
            try {
              const r = await fetch('/api/v1/config/backup', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'x-user-id': localStorage.getItem('mcp_hub_user') || 'anonymous' },
                body: JSON.stringify({ label: '' }),
              }).then(r => r.json())
              setMessage(r.success ? '✅ 配置已备份' : `❌ ${r.message}`)
            } catch { setMessage('❌ 备份失败') }
          }}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors">
          💾 备份配置
          </button>
          <button onClick={async () => {
            try {
              const r = await fetch('/api/v1/config/diff', {
                headers: { 'x-user-id': localStorage.getItem('mcp_hub_user') || 'anonymous' },
              }).then(r => r.json())
              if (r.data) {
                const d = r.data
                if (d.in_sync) setMessage('✅ 配置与 Hub 完全同步')
                else setMessage(`⚠️ 差异: 本地${d.only_local.length}个独有, Hub${d.only_hub.length}个独有, ${d.different.length}个不一致`)
              }
            } catch { setMessage('❌ 差异检查失败') }
          }}
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors">
          🔍 检查差异
          </button>
          <button onClick={handleDownload} disabled={downloading}
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors disabled:opacity-50">
          🔄 同步到本地
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
