import { useState } from 'react'
import { uploadConfig, downloadConfig } from '../api/client'

export default function ConfigPage() {
  const [uploadResult, setUploadResult] = useState<any>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_upload_result') || 'null') } catch { return null }
  })
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [downloadError, setDownloadError] = useState('')

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setDownloadError('')
    try {
      const r = await uploadConfig(file)
      setUploadResult(r)
      localStorage.setItem('mcp_hub_upload_result', JSON.stringify(r))
    } catch (err: any) {
      const errMsg = { success: false, message: err.message || '上传失败' }
      setUploadResult(errMsg)
    } finally {
      setUploading(false)
    }
  }

  const handleDownload = async () => {
    setDownloadError('')
    try {
      const blob = await downloadConfig()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url; a.download = 'mcp-hub-config.json'; a.click()
      URL.revokeObjectURL(url)
    } catch (err: any) {
      setDownloadError('❌ 下载失败: ' + (err.message || '未知错误'))
    }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">⚙️ 配置管理</h1>
      <p className="text-gray-500">导入/导出现有的 MCP 配置，绑定你本地的 Agent</p>

      {/* Download */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-2">📥 下载当前配置</h2>
        <p className="text-sm text-gray-500 mb-4">将所有已安装的 Server 导出为 mcp.json，导入到本地 Agent</p>
        <button onClick={handleDownload} className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
          下载 mcp-hub-config.json
        </button>
        {downloadError && (
          <p className="mt-2 text-sm text-red-600">{downloadError}</p>
        )}
      </div>

      {/* Upload */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-2">📤 上传本地配置</h2>
        <p className="text-sm text-gray-500 mb-4">上传你本地的 claude_desktop_config.json 或 mcp.json，Hub 会分析并推荐可安装的 Server</p>
        <label
          className={`block border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => { e.preventDefault(); setDragging(false); const f = e.dataTransfer.files[0]; if (f) { const dt = new DataTransfer(); dt.items.add(f); const input = document.createElement('input'); input.type = 'file'; input.files = dt.files; const ev = new Event('change', { bubbles: true }); input.dispatchEvent(ev); handleUpload(ev as any) } }}
        >
          <input type="file" accept=".json" onChange={handleUpload} className="hidden" />
          <div className="text-4xl mb-2">{uploading ? '⏳' : '📂'}</div>
          <p className="text-gray-600">{uploading ? '正在上传...' : '拖拽 JSON 文件到此处，或点击选择'}</p>
          <p className="text-xs text-gray-400 mt-1">支持 claude_desktop_config.json / mcp.json</p>
        </label>

        {uploadResult && (
          <div className="mt-4 p-3 rounded-lg text-sm space-y-1" style={{ backgroundColor: uploadResult.success !== false ? '#EFF6FF' : '#FEF2F2', color: uploadResult.success !== false ? '#1D4ED8' : '#991B1B' }}>
            <p>{uploadResult.message || (uploadResult.success !== false ? '配置上传成功' : '上传失败')}</p>
            {uploadResult.data?.matched?.length > 0 && (
              <div className="mt-2">
                <p className="font-medium">✅ 可在 Hub 中安装的：</p>
                {uploadResult.data.matched.map((m: any) => (
                  <p key={m.local_name} className="ml-2">• {m.local_name} → {m.hub_install_command || m.local_command}</p>
                ))}
              </div>
            )}
            {uploadResult.data?.unmatched?.length > 0 && (
              <div className="mt-2">
                <p className="font-medium text-yellow-700">⚠️ 未匹配的：</p>
                {uploadResult.data.unmatched.slice(0, 5).map((m: any) => (
                  <p key={m.local_name} className="ml-2">• {m.local_name}</p>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 同步到本地 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-2">🔄 同步到本地</h2>
        <p className="text-sm text-gray-500 mb-4">将 Hub 配置一键同步到本地 Agent 配置文件</p>
        <div className="flex items-center gap-3 flex-wrap">
          <div className="relative group">
            <button
              onClick={async () => {
                try {
                  const blob = await downloadConfig()
                  const url = URL.createObjectURL(blob)
                  const a = document.createElement('a')
                  a.href = url; a.download = 'mcp-hub-config.json'; a.click()
                  URL.revokeObjectURL(url)
                } catch {}
              }}
              className="p-2.5 rounded-lg bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-800 transition-colors"
              title="下载配置包"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
                <polyline points="7 10 12 15 17 10"/>
                <line x1="12" y1="15" x2="12" y2="3"/>
              </svg>
            </button>
            <span className="absolute -top-8 left-1/2 -translate-x-1/2 bg-gray-800 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
              下载配置
            </span>
          </div>
          <span className="text-sm text-gray-500">或使用命令行: <code className="px-2 py-0.5 bg-gray-100 rounded text-xs">mcp config sync --server {window.location.origin}</code></span>
        </div>
      </div>
    </div>
  )
}
