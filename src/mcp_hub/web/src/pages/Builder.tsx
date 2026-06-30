import { useState, useEffect } from 'react'

interface Tool {
  name: string
  description: string
  params: Array<{ name: string; type: string; description: string }>
}

const STORAGE_KEY = 'mcp_hub_builder_form'

function loadForm() {
  try {
    const saved = sessionStorage.getItem(STORAGE_KEY)
    if (saved) return JSON.parse(saved)
  } catch {}
  return null
}

function saveForm(data: any) {
  try { sessionStorage.setItem(STORAGE_KEY, JSON.stringify(data)) } catch {}
}

export default function Builder() {
  const saved = loadForm()
  const [name, setName] = useState(saved?.name || 'my-mcp-server')
  const [language, setLanguage] = useState<'python' | 'typescript'>(saved?.language || 'python')
  const [description, setDescription] = useState(saved?.description || '')
  const [author, setAuthor] = useState(saved?.author || '')
  const [selectedTools, setSelectedTools] = useState<Set<string>>(new Set(saved?.tools || ['hello', 'echo']))
  const [availableTools, setAvailableTools] = useState<Tool[]>([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // 自动保存表单状态到 sessionStorage
  useEffect(() => {
    saveForm({
      name, language, description, author,
      tools: Array.from(selectedTools),
    })
  }, [name, language, description, author, selectedTools])

  useEffect(() => {
    fetch('/api/v1/builder/tools')
      .then(r => r.json())
      .then(r => { if (r.data) setAvailableTools(r.data) })
      .catch(() => setError('无法加载工具模板列表'))
      .finally(() => setLoading(false))
  }, [])

  const toggleTool = (toolName: string) => {
    setSelectedTools(prev => {
      const next = new Set(prev)
      if (next.has(toolName)) next.delete(toolName)
      else next.add(toolName)
      return next
    })
  }

  const handleDownload = async () => {
    if (!name.trim()) { setError('请输入项目名称'); return }
    setError('')
    setSuccess('')
    setDownloading(true)
    try {
      const tools = Array.from(selectedTools).join(',')
      const params = new URLSearchParams({
        name: name.trim(),
        language,
        description: description || `MCP Server: ${name}`,
        author: author || 'developer',
        tools,
      })
      const res = await fetch(`/api/v1/builder/generate?${params}`)
      if (!res.ok) {
        const errText = await res.text().catch(() => '')
        throw new Error(errText ? `服务器错误: ${errText}` : `生成失败 (${res.status})`)
      }
      const blob = await res.blob()
      if (blob.size === 0) throw new Error('生成的文件为空')
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${name.trim()}.zip`
      a.click()
      URL.revokeObjectURL(url)
      setSuccess(`✅ 项目 "${name}" 已生成并下载`)
      setTimeout(() => setSuccess(''), 5000)
    } catch (e: any) {
      setError('❌ ' + (e.message || '下载失败'))
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <div className="flex items-center gap-3 mb-6">
        <span className="text-3xl">🛠️</span>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">MCP Server Builder</h1>
          <p className="text-sm text-gray-500">在线生成 MCP Server 项目，下载 ZIP 直接使用</p>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700">
          {error}
          <button onClick={() => setError('')} className="float-right text-red-400 hover:text-red-600">✕</button>
        </div>
      )}
      {success && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-sm text-green-700">
          {success}
        </div>
      )}

      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        {/* 项目名称 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">项目名称 *</label>
          <input type="text" value={name} onChange={e => setName(e.target.value)}
            placeholder="my-mcp-server"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>

        {/* 语言 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">语言</label>
          <div className="flex gap-2">
            <button onClick={() => setLanguage('python')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${language === 'python' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              🐍 Python
            </button>
            <button onClick={() => setLanguage('typescript')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${language === 'typescript' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
              📘 TypeScript
            </button>
          </div>
        </div>

        {/* 描述 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
          <input type="text" value={description} onChange={e => setDescription(e.target.value)}
            placeholder="MCP Server: my-mcp-server"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>

        {/* 作者 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">作者</label>
          <input type="text" value={author} onChange={e => setAuthor(e.target.value)}
            placeholder="developer"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>

        {/* 工具选择 */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">工具模板 <span className="text-gray-400 font-normal">（至少要选一个）</span></label>
          {loading ? (
            <div className="text-sm text-gray-400">加载中...</div>
          ) : error ? (
            <div className="text-sm text-red-400">⚠️ {error}</div>
          ) : availableTools.length === 0 ? (
            <div className="text-sm text-gray-400">暂无可用的工具模板</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {availableTools.map(tool => (
                <button key={tool.name} onClick={() => toggleTool(tool.name)}
                  className={`text-left px-3 py-2 rounded-lg border text-sm transition-colors ${
                    selectedTools.has(tool.name)
                      ? 'border-blue-500 bg-blue-50 text-blue-700'
                      : 'border-gray-200 bg-white text-gray-600 hover:border-gray-300'
                  }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{tool.name}</span>
                    <span>{selectedTools.has(tool.name) ? '✓' : ''}</span>
                  </div>
                  <p className="text-xs text-gray-400 mt-0.5">{tool.description}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        {/* 下载按钮 */}
        <button onClick={handleDownload} disabled={!name.trim() || downloading || selectedTools.size === 0}
          className="w-full py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
          {downloading ? '⏳ 生成中...' : '📥 下载项目 ZIP'}
        </button>

        <p className="text-xs text-gray-400 text-center">
          生成的项目包含完整的 MCP Server 代码、README、配置文件，可直接发布到 PyPI/npm
        </p>
      </div>
    </div>
  )
}
