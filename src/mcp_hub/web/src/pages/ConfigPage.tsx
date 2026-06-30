import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadConfig, downloadConfig, apiGet } from '../api/client'

const AGENTS = [
  { id: 'claude-code', name: 'Claude Code', path: '~/.config/Claude/claude_desktop_config.json', icon: '🤖' },
  { id: 'cursor', name: 'Cursor', path: '~/.cursor/mcp.json', icon: '📝' },
  { id: 'codex', name: 'Codex', path: '~/.codex/mcp.json', icon: '🔧' },
  { id: 'trae', name: 'Trae', path: '~/.trae/mcp.json', icon: '🚀' },
  { id: 'generic', name: '通用 mcp.json', path: './mcp.json', icon: '📄' },
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
  const [showCliHint, setShowCliHint] = useState(false)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>, agentOverride?: string) => {
    const file = e.target.files?.[0]
    if (!file) return
    const agent = agentOverride || selectedAgent
    setUploading(true)
    setMessage('')
    try {
      const r = await uploadConfig(file, agent)
      setUploadResult(r)
      localStorage.setItem('mcp_hub_upload_result', JSON.stringify(r))
      if (r.success) {
        setMessage(`✅ ${r.data?.server_count || 0} 个 Server 已同步到配置（${AGENTS.find(a => a.id === agent)?.name || agent}）`)
        setTimeout(() => navigate('/my-servers'), 1500)
      }
    } catch (err: any) {
      setUploadResult({ success: false, message: err.message || '上传失败' })
    } finally { setUploading(false) }
  }

  const handleDownloadForAgent = async (agentId?: string) => {
    const aid = agentId || selectedAgent
    setDownloading(true)
    setMessage('')
    try {
      // 使用 API 生成对应 Agent 格式的配置
      const blob = await apiGet<any>(`/export/config?agent=${aid}&share=false`)
        .then(r => {
          // 如果 API 返回 JSON, 转成 Blob
          if (r.data) return new Blob([JSON.stringify(r.data, null, 2)], { type: 'application/json' })
          throw new Error('生成失败')
        })
        .catch(() => downloadConfig()) // 回退到通用下载
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `mcp-hub-config-${aid}.json`
      a.click()
      URL.revokeObjectURL(url)
      const agent = AGENTS.find(a => a.id === aid)
      setMessage(`✅ 配置已下载！请将文件保存到: ${agent?.path || '本地目录'}`)
    } catch (err: any) {
      setMessage('❌ 下载失败: ' + (err.message || ''))
    } finally { setDownloading(false) }
  }

  const agent = AGENTS.find(a => a.id === selectedAgent)

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">⚙️ 配置中心</h1>
      <p className="text-gray-500">上传现有配置、选择你的 Agent、下载写好的配置文件，三步完成接入</p>

      {/* 三步流程图 */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {[
          { step: '1', title: '上传本地配置', desc: '上传你现有的 claude_desktop_config.json，Hub 自动识别你用了哪些 Server', icon: '📤' },
          { step: '2', title: '选择你的 Agent', desc: '选择你要接入的 AI 客户端，不同 Agent 配置格式略有不同', icon: '🎯' },
          { step: '3', title: '下载并替换', desc: '下载后替换本地的配置文件，重启 Agent 即可生效', icon: '📥' },
        ].map(s => (
          <div key={s.step} className="bg-white rounded-xl border border-gray-200 p-4">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-2">{s.step}</span>
            <h3 className="font-medium text-gray-900 text-sm mb-1">{s.title}</h3>
            <p className="text-xs text-gray-500">{s.desc}</p>
          </div>
        ))}
      </div>

      {/* 步骤1: 上传 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">📤 步骤 1：上传现有配置</h2>
        <p className="text-sm text-gray-500 mb-4">上传你本地的 claude_desktop_config.json，Hub 会自动匹配市场中的 Server</p>
        <label
          className={`block border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition-colors ${dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) { const dt = new DataTransfer(); dt.items.add(f); const input = document.createElement('input'); input.type = 'file'; input.files = dt.files; const ev = new Event('change', { bubbles: true }); input.dispatchEvent(ev); handleUpload(ev as any) } }}
        >
          <input type="file" accept=".json" onChange={handleUpload} className="hidden" />
          <div className="text-3xl mb-1">{uploading ? '⏳' : '📂'}</div>
          <p className="text-gray-600 text-sm">{uploading ? '正在上传...' : '拖拽 JSON 文件到此处，或点击选择'}</p>
        </label>
        {uploadResult && (
          <div className="mt-3 p-3 rounded-lg text-sm" style={{ backgroundColor: uploadResult.success !== false ? '#EFF6FF' : '#FEF2F2', color: uploadResult.success !== false ? '#1D4ED8' : '#991B1B' }}>
            <p>{uploadResult.message || (uploadResult.success !== false ? '配置上传成功' : '上传失败')}</p>
            {uploadResult.data?.matched?.length > 0 && (
              <div className="mt-1 text-xs">
                <p className="font-medium">✅ 匹配到 {uploadResult.data.matched.length} 个 Hub Server：</p>
                {uploadResult.data.matched.map((m: any) => <p key={m.local_name} className="ml-2">• {m.local_name}</p>)}
              </div>
            )}
            {uploadResult.data?.unmatched?.length > 0 && (
              <div className="mt-1 text-xs">
                <p className="font-medium text-yellow-700">⚠️ {uploadResult.data.unmatched.length} 个未匹配：</p>
                {uploadResult.data.unmatched.slice(0, 5).map((m: any) => <p key={m.local_name} className="ml-2">• {m.local_name}</p>)}
              </div>
            )}
            <button onClick={() => { setUploadResult(null); localStorage.removeItem('mcp_hub_upload_result') }}
              className="mt-2 text-xs text-blue-600 hover:text-blue-800">清除结果</button>
          </div>
        )}
      </div>

      {/* 步骤2+3: 选择Agent + 下载 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-1">🎯 步骤 2：选择你的 Agent</h2>
        <p className="text-sm text-gray-500 mb-4">选择你使用的 AI 客户端，Hub 会生成对应格式的配置文件</p>
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

        <div className="bg-gray-50 rounded-lg p-4 mb-4">
          <p className="text-xs text-gray-500 mb-1">文件保存位置：</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 px-3 py-2 bg-gray-900 text-green-400 rounded-lg text-xs font-mono truncate">
              {agent?.path || '~/.config/claude_desktop_config.json'}
            </code>
            <button onClick={() => { navigator.clipboard.writeText(agent?.path || ''); setMessage('✅ 路径已复制') }}
              className="px-3 py-2 bg-gray-700 text-white rounded-lg text-xs hover:bg-gray-600 transition-colors flex-shrink-0">
              📋 复制路径
            </button>
          </div>
        </div>

        <button onClick={() => handleDownloadForAgent()} disabled={downloading}
          className="w-full py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-medium transition-colors disabled:opacity-50 mb-2">
          {downloading ? '⏳ 生成中...' : `📥 下载 ${agent?.name || ''} 配置文件`}
        </button>
        {message && (
          <div className={`p-3 rounded-lg text-sm ${message.startsWith('✅') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
            {message}
          </div>
        )}
      </div>

      {/* 命令行同步（高级选项） */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between cursor-pointer" onClick={() => setShowCliHint(!showCliHint)}>
          <h2 className="font-semibold text-gray-900">🖥️ 命令行同步（高级）</h2>
          <span className="text-gray-400 text-sm">{showCliHint ? '收起' : '展开'}</span>
        </div>
        {showCliHint && (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-gray-500">如果你安装了 <code className="px-1 bg-gray-100 rounded text-xs">mcp-hub-cli</code>，可以使用以下命令一键同步配置到本地：</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 bg-gray-900 rounded-lg p-3 overflow-x-auto">
                <pre className="text-green-400 text-xs font-mono">mcp config sync --server {window.location.origin}</pre>
              </div>
              <button onClick={() => { navigator.clipboard.writeText(`mcp config sync --server ${window.location.origin}`); setMessage('✅ 命令已复制，在终端中粘贴运行') }}
                className="px-4 py-3 bg-gray-800 text-white rounded-lg text-xs hover:bg-gray-700 transition-colors flex-shrink-0">
                📋 复制命令
              </button>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
              <p className="font-medium">💡 提示</p>
              <p>命令行方式支持自动写入本地文件（无需手动拖放），适合经常更新配置的用户。需要先在本地安装：<code className="px-1 bg-yellow-100 rounded">pip install mcp-hub-cli</code></p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
