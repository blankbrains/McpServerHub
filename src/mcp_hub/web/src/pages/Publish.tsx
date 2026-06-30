import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface PublishForm {
  name: string
  description: string
  category: string
  installType: string
  installCommand: string
  homepage: string
  tags: string
}

interface PublishedServer {
  id: string
  name: string
  description: string
  version: string
  rating: number
  download_count: number
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

function loadForm(): PublishForm {
  try {
    const saved = sessionStorage.getItem('mcp_hub_publish_form')
    if (saved) return JSON.parse(saved)
  } catch {}
  return { name: '', description: '', category: 'tools', installType: 'npx', installCommand: '', homepage: '', tags: '' }
}

export default function Publish() {
  const [form, setForm] = useState<PublishForm>(loadForm)
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [published, setPublished] = useState<PublishedServer[]>([])
  const [publishedLoading, setPublishedLoading] = useState(true)
  const userId = localStorage.getItem('mcp_hub_user') || ''

  const saveForm = (data: PublishForm) => {
    try { sessionStorage.setItem('mcp_hub_publish_form', JSON.stringify(data)) } catch {}
  }

  // 加载已发布的 Server
  const loadPublished = async () => {
    if (!userId) { setPublishedLoading(false); return }
    try {
      const res = await fetch('/api/v1/publish/mine', {
        headers: { 'x-user-id': userId },
      })
      const r = await res.json()
      if (r.data) setPublished(r.data)
    } catch {}
    finally { setPublishedLoading(false) }
  }

  useEffect(() => { loadPublished() }, [])

  const handleChange = (field: keyof PublishForm, value: string) => {
    const next = { ...form, [field]: value }
    setForm(next)
    saveForm(next)
  }

  const handleSubmit = async () => {
    if (!form.name.trim()) { setStatus('error'); setMessage('请输入 Server 名称'); return }
    if (!form.installCommand.trim()) { setStatus('error'); setMessage('请输入安装命令'); return }

    setStatus('submitting')
    try {
      const body = {
        name: form.name.trim(),
        description: form.description.trim(),
        category: form.category,
        install_type: form.installType,
        install_command: form.installCommand.trim(),
        homepage: form.homepage.trim(),
        tags: form.tags.split(',').map(t => t.trim()).filter(Boolean),
      }
      const res = await fetch('/api/v1/publish', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-user-id': userId || 'anonymous' },
        body: JSON.stringify(body),
      })
      const data = await res.json()
      if (data.success) {
        setStatus('success')
        setMessage(`✅ Server "${form.name}" 发布成功！`)
        const empty = { name: '', description: '', category: 'tools', installType: 'npx', installCommand: '', homepage: '', tags: '' }
        setForm(empty); saveForm(empty)
        loadPublished() // 刷新已发布列表
      } else {
        setStatus('error')
        setMessage(data.error?.message || data.message || '发布失败')
      }
    } catch {
      setStatus('error')
      setMessage('网络错误，请稍后重试')
    }
  }

  const handleUnpublish = async (serverId: string) => {
    if (!window.confirm(`确定要下架 "${serverId}" 吗？`)) return
    try {
      const res = await fetch(`/api/v1/publish/unpublish/${encodeURIComponent(serverId)}`, {
        method: 'POST',
        headers: { 'x-user-id': userId },
      })
      const r = await res.json()
      if (r.success) {
        setPublished(prev => prev.filter(s => s.id !== serverId))
        setMessage(`✅ ${serverId} 已下架`)
      } else {
        setMessage('❌ ' + (r.error || '下架失败'))
      }
    } catch {
      setMessage('❌ 网络错误')
    }
    setTimeout(() => setMessage(''), 3000)
  }

  return (
    <div className="max-w-2xl mx-auto py-8 px-4 space-y-8">
      <h1 className="text-2xl font-bold text-gray-800 mb-2">发布 MCP Server</h1>
      <p className="text-sm text-gray-500 mb-8">
        将你的 MCP Server 提交到 Hub 市场，让更多开发者发现和使用
      </p>

      {status === 'success' && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm space-y-1">
          <p>{message}</p>
          <Link to="/my-config" className="inline-block text-sm text-green-600 underline hover:text-green-800">去「我的配置」查看</Link>
        </div>
      )}
      {status === 'error' && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{message}</div>
      )}

      {/* 发布表单 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 space-y-5">
        <h2 className="font-semibold text-gray-900">📝 填写 Server 信息</h2>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Server 名称 <span className="text-red-500">*</span></label>
          <input type="text" value={form.name} onChange={e => handleChange('name', e.target.value)}
            placeholder="例: @myorg/my-mcp-server"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">描述</label>
          <textarea value={form.description} onChange={e => handleChange('description', e.target.value)}
            placeholder="简要描述这个 Server 的功能..." rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none" />
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">分类</label>
            <select value={form.category} onChange={e => handleChange('category', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none">
              {CATEGORIES.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">安装方式</label>
            <select value={form.installType} onChange={e => handleChange('installType', e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none">
              {INSTALL_TYPES.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">安装命令 <span className="text-red-500">*</span></label>
          <input type="text" value={form.installCommand} onChange={e => handleChange('installCommand', e.target.value)}
            placeholder="例: npx -y @myorg/my-mcp-server"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">主页 URL</label>
          <input type="url" value={form.homepage} onChange={e => handleChange('homepage', e.target.value)}
            placeholder="https://github.com/..."
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">标签 <span className="text-gray-400 font-normal">（逗号分隔）</span></label>
          <input type="text" value={form.tags} onChange={e => handleChange('tags', e.target.value)}
            placeholder="例: web, search, api"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm outline-none focus:ring-2 focus:ring-blue-500" />
        </div>

        <button onClick={handleSubmit} disabled={status === 'submitting'}
          className="w-full py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 transition-colors font-medium disabled:opacity-50">
          {status === 'submitting' ? '提交中...' : '发布 Server'}
        </button>
      </div>

      {/* 已发布列表 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-4">📦 我发布的 Server</h2>
        {!userId ? (
          <p className="text-sm text-gray-400">请先 <Link to="/login" className="text-blue-600 underline">登录</Link> 后查看已发布的 Server</p>
        ) : publishedLoading ? (
          <p className="text-sm text-gray-400">加载中...</p>
        ) : published.length === 0 ? (
          <div className="text-center py-6 text-gray-400 text-sm">
            <p>还没有发布过 Server</p>
            <p className="mt-1">填写上方表单发布你的第一个 MCP Server</p>
          </div>
        ) : (
          <div className="space-y-2">
            {published.map(s => (
              <div key={s.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="min-w-0">
                  <Link to={`/servers/${encodeURIComponent(s.id)}`} className="text-sm font-medium text-gray-900 hover:text-blue-600 truncate block">
                    {s.id}
                  </Link>
                  <p className="text-xs text-gray-400">v{s.version || '?'} · ⭐{s.rating} · 📥{s.download_count}</p>
                </div>
                <button onClick={() => handleUnpublish(s.id)}
                  className="ml-2 px-3 py-1 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors flex-shrink-0">
                  下架
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
