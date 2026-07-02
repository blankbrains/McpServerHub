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

export default function ConfigPage() {
  const [uploadResult, setUploadResult] = useState<any>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_upload_result') || 'null') } catch { return null }
  })
  const navigate = useNavigate()
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [selectedAgent, setSelectedAgent] = useState('claude-code')
  const [downloading, setDownloading] = useState(false)
  const [message, setMessage] = useState('')
  const [previewData, setPreviewData] = useState<any>(null)
  const [pendingFile, setPendingFile] = useState<File | null>(null)

  // Step 1: 选择文件 → 本地解析预览（不直接上传）
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setPendingFile(file)
    setMessage('')
    setUploadResult(null)
    try {
      const text = await file.text()
      const json = JSON.parse(text)
      const servers = json.mcpServers || {}
      const names = Object.keys(servers)
      if (names.length === 0) { setMessage('⚠️ 配置文件中未找到 mcpServers 定义'); return }
      setPreviewData({ fileName: file.name, serverCount: names.length, servers: names })
    } catch {
      setMessage('❌ 文件格式无效，请上传 JSON 文件')
      setPreviewData(null)
      setPendingFile(null)
    }
  }

  // Step 2: 确认上传
  const handleConfirmUpload = async () => {
    if (!pendingFile) return
    setUploading(true)
    setMessage('')
    try {
      const r = await uploadConfig(pendingFile, selectedAgent)
      setUploadResult(r)
      setPreviewData(null)
      setPendingFile(null)
      localStorage.setItem('mcp_hub_upload_result', JSON.stringify(r))
      if (r.success) {
        setMessage(`✅ 上传成功！${r.data?.server_count || 0} 个 Server 已添加到你的配置`)
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

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const blob = await downloadConfig()
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
      <p className="text-gray-500 text-sm">上传你的 mcp.json → 选择 Agent → Hub 自动匹配并监控你的 MCP 调用</p>

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
              上传后，Hub 会在市场匹配并自动添加到「我的 Server」
            </p>
            <div className="flex gap-2">
              <button onClick={handleConfirmUpload} className="px-6 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
                ✅ 确认上传
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

        {/* 上传结果 */}
        {uploadResult && (
          <div className="mt-4 p-3 rounded-lg text-sm" style={{
            backgroundColor: uploadResult.success !== false ? '#EFF6FF' : '#FEF2F2',
            color: uploadResult.success !== false ? '#1D4ED8' : '#991B1B'
          }}>
            <p className="font-medium">{uploadResult.message || (uploadResult.success !== false ? '配置上传成功' : '上传失败')}</p>
            {uploadResult.data?.matched?.length > 0 && (
              <div className="mt-1 text-xs space-y-0.5">
                <p>✅ Hub 已匹配 <strong>{uploadResult.data.matched.length}</strong> 个 Server：</p>
                {uploadResult.data.matched.map((m: any) => (
                  <p key={m.local_name} className="ml-2">• {m.local_name} → {m.hub_id}</p>
                ))}
              </div>
            )}
            {uploadResult.data?.unmatched?.length > 0 && (
              <div className="mt-1 text-xs space-y-0.5">
                <p className="text-yellow-700">⚠️ <strong>{uploadResult.data.unmatched.length}</strong> 个已注册为自定义：</p>
                {uploadResult.data.unmatched.slice(0, 5).map((m: any) => (
                  <p key={m.local_name} className="ml-2">• {m.local_name}</p>
                ))}
              </div>
            )}
            <div className="flex gap-2 mt-2">
              <button onClick={() => navigate('/my-servers')}
                className="px-3 py-1 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700">
                去「我的 Server」查看 →
              </button>
              <button onClick={() => { setUploadResult(null); localStorage.removeItem('mcp_hub_upload_result') }}
                className="px-3 py-1 bg-white text-gray-600 border rounded-lg text-xs hover:bg-gray-50">
                清除结果
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── 步骤 2：选择 Agent 工具 ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">🎯 步骤 2：选择你的 AI Agent 工具</h2>
        <p className="text-sm text-gray-500 mb-4">
          上传配置后选择你使用的 Agent，Hub 会记录该 Agent 下的 MCP 调用数据
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

        {/* 下载配置文件（生成 Agent 可用的 mcp.json） */}
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

      {/* ── 步骤 3：启用监控 ── */}
      <div className="bg-white rounded-xl border border-green-200 bg-green-50 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">📊 步骤 3：启用调用监控</h2>
        <p className="text-sm text-gray-600 mb-4">
          要监控 Agent 中的 MCP 调用，需要将 Hub 网关作为中间人代理。
          在你本机的 Agent 配置文件 <strong>末尾</strong>添加以下内容：
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
          添加后，所有 MCP 工具调用都会经过 Hub 网关，调用次数、响应时长、Token 消耗将自动记录到监控大屏
        </p>
        <button onClick={() => { navigator.clipboard.writeText('"mcp-hub-gateway": {\n  "command": "mcp",\n  "args": ["serve"]\n}'); setMessage('✅ 已复制到剪贴板') }}
          className="px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors">
          📋 复制配置
        </button>
      </div>

      {/* ── 高级功能：备份/差异/同步 ── */}
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
