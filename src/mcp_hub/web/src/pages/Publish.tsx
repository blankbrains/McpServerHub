import { useState } from 'react'

interface PublishForm {
  name: string
  description: string
  category: string
  installType: string
  installCommand: string
  homepage: string
  tags: string
}

const CATEGORIES = [
  { id: 'browser', name: '浏览器 & 搜索' },
  { id: 'database', name: '数据库' },
  { id: 'developer-tools', name: '开发者工具' },
  { id: 'ai', name: 'AI & 机器学习' },
  { id: 'communication', name: '通信 & 协作' },
  { id: 'cloud', name: '云服务 & DevOps' },
  { id: 'monitoring', name: '监控 & 调试' },
  { id: 'storage', name: '存储 & 文件' },
  { id: 'security', name: '安全 & 合规' },
  { id: 'finance', name: '金融 & 支付' },
  { id: 'maps', name: '地图 & 位置' },
  { id: 'design', name: '设计 & 媒体' },
  { id: 'social-media', name: '社交媒体' },
  { id: 'productivity', name: '效率 & 笔记' },
  { id: 'apis', name: 'API & 集成' },
  { id: 'tools', name: '通用 & 其他' },
]

const INSTALL_TYPES = [
  { id: 'npx', name: 'npx (Node.js)' },
  { id: 'pip', name: 'pip (Python)' },
  { id: 'uvx', name: 'uvx (Python)' },
]

export default function Publish() {
  const [form, setForm] = useState<PublishForm>({
    name: '',
    description: '',
    category: 'tools',
    installType: 'npx',
    installCommand: '',
    homepage: '',
    tags: '',
  })
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleChange = (field: keyof PublishForm, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }))
  }

  const handleSubmit = async () => {
    if (!form.name.trim() || !form.installCommand.trim()) {
      setStatus('error')
      setMessage('请填写 Server 名称和安装命令')
      return
    }

    setStatus('submitting')
    try {
      const res = await fetch('/api/v1/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: form.name.trim(),
          description: form.description.trim(),
          category: form.category,
          install_type: form.installType,
          install_command: form.installCommand.trim(),
          homepage: form.homepage.trim(),
          tags: form.tags
            .split(',')
            .map(t => t.trim())
            .filter(Boolean),
        }),
      })
      const data = await res.json()
      if (data.success) {
        setStatus('success')
        setMessage(`✅ Server "${form.name}" 发布成功！`)
        setForm({
          name: '',
          description: '',
          category: 'tools',
          installType: 'npx',
          installCommand: '',
          homepage: '',
          tags: '',
        })
      } else {
        setStatus('error')
        setMessage(data.error?.message || '发布失败')
      }
    } catch {
      setStatus('error')
      setMessage('网络错误，请稍后重试')
    }
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4">
      <h1 className="text-2xl font-bold text-gray-800 mb-2">发布 MCP Server</h1>
      <p className="text-sm text-gray-500 mb-8">
        将你的 MCP Server 提交到 Hub 市场，让更多开发者发现和使用
      </p>

      {status === 'success' && (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">
          {message}
        </div>
      )}
      {status === 'error' && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
          {message}
        </div>
      )}

      <div className="space-y-5">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Server 名称 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.name}
            onChange={e => handleChange('name', e.target.value)}
            placeholder="例: @myorg/my-mcp-server"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
          <textarea
            value={form.description}
            onChange={e => handleChange('description', e.target.value)}
            placeholder="简要描述这个 Server 的功能..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none resize-none"
          />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
            <select
              value={form.category}
              onChange={e => handleChange('category', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            >
              {CATEGORIES.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">安装方式</label>
            <select
              value={form.installType}
              onChange={e => handleChange('installType', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
            >
              {INSTALL_TYPES.map(t => (
                <option key={t.id} value={t.id}>{t.name}</option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            安装命令 <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            value={form.installCommand}
            onChange={e => handleChange('installCommand', e.target.value)}
            placeholder="例: npx -y @myorg/my-mcp-server"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none font-mono"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">主页 URL</label>
          <input
            type="url"
            value={form.homepage}
            onChange={e => handleChange('homepage', e.target.value)}
            placeholder="https://github.com/..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            标签 <span className="text-gray-400 font-normal">（逗号分隔）</span>
          </label>
          <input
            type="text"
            value={form.tags}
            onChange={e => handleChange('tags', e.target.value)}
            placeholder="例: web, search, api"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent outline-none"
          />
        </div>

        <button
          onClick={handleSubmit}
          disabled={status === 'submitting'}
          className="w-full py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {status === 'submitting' ? '提交中...' : '发布 Server'}
        </button>
      </div>
    </div>
  )
}
