import { useState } from 'react'
import { uploadConfig, downloadConfig } from '../api/client'

export default function ConfigPage() {
  const [uploadResult, setUploadResult] = useState<any>(null)
  const [dragging, setDragging] = useState(false)

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const r = await uploadConfig(file)
    setUploadResult(r)
  }

  const handleDownload = async () => {
    const blob = await downloadConfig()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = 'mcp-hub-config.json'; a.click()
    URL.revokeObjectURL(url)
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
          <div className="text-4xl mb-2">📂</div>
          <p className="text-gray-600">拖拽 JSON 文件到此处，或点击选择</p>
          <p className="text-xs text-gray-400 mt-1">支持 claude_desktop_config.json / mcp.json</p>
        </label>

        {uploadResult && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-700">
            {uploadResult.message}
            {uploadResult.data?.servers && (
              <ul className="mt-2 list-disc list-inside">
                {uploadResult.data.servers.map((s: string) => <li key={s}>{s}</li>)}
              </ul>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
