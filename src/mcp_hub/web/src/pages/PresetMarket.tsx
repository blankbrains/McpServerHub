import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { ApiRequestError, apiGet, apiPost } from '../api/client'
import { useAuthState } from '../hooks/useAuthState'

interface Preset {
  id: number
  user_id: string
  name: string
  description: string
  tags: string[]
  servers: any[]
  server_count: number
  download_count: number
  rating: number
  created_at: string
}

export default function PresetMarket() {
  const { token, userId } = useAuthState()
  const [presets, setPresets] = useState<Preset[]>([])
  const [loading, setLoading] = useState(true)
  const [showCreate, setShowCreate] = useState(false)
  const [message, setMessage] = useState('')
  const [messageType, setMessageType] = useState<'success' | 'error'>('success')
  const [loadError, setLoadError] = useState('')
  const [importing, setImporting] = useState<Set<number>>(new Set())
  const [creating, setCreating] = useState(false)
  const [sort, setSort] = useState('hot')
  // 创建表单
  const [newName, setNewName] = useState('')
  const [newDesc, setNewDesc] = useState('')
  const [newTags, setNewTags] = useState('')
  const load = async () => {
    setLoading(true)
    setLoadError('')
    try {
      const result = await apiGet<Preset[]>(`/presets?sort=${encodeURIComponent(sort)}`)
      setPresets(result.data || [])
    } catch {
      setPresets([])
      setLoadError('方案市场加载失败，请稍后重试')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [sort])

  const handleCreate = async () => {
    if (!token || !userId) {
      setMessageType('error')
      setMessage('请先登录后再发布方案')
      return
    }
    if (!newName.trim()) {
      setMessageType('error')
      setMessage('请输入方案名称')
      return
    }
    setCreating(true)
    try {
      const myServers = await apiGet<any[]>('/config/user-servers')
      const trackedServers = (myServers.data || [])
        .map((server: any) => ({
          server_id: server.hub_id || server.name,
          name: server.name,
          matched: server.matched !== false,
        }))
        .filter((server: any) => Boolean(server.server_id))

      if (trackedServers.length === 0) {
        setMessageType('error')
        setMessage('还没有追踪任何 Server，请先在市场添加或在配置中心确认追踪')
        return
      }

      const r: any = await apiPost('/presets', {
        name: newName.trim(),
        description: newDesc.trim(),
        tags: newTags.split(',').map(t => t.trim()).filter(Boolean),
        servers: trackedServers,
      })
      if (r.success) {
        setMessageType('success')
        setMessage(`方案已发布，包含 ${trackedServers.length} 个追踪 Server`)
        setShowCreate(false); setNewName(''); setNewDesc(''); setNewTags('')
        await load()
      } else {
        setMessageType('error')
        setMessage(typeof r.error === 'string' ? r.error : '发布失败')
      }
    } catch (error) {
      setMessageType('error')
      setMessage(error instanceof ApiRequestError && error.status === 401 ? '登录状态已失效，请重新登录' : '发布失败，请稍后重试')
    } finally {
      setCreating(false)
    }
  }

  const handleImport = async (preset: Preset) => {
    if (!token || !userId) {
      setMessageType('error')
      setMessage('请先登录后再导入方案')
      return
    }
    if (!window.confirm(`导入"${preset.name}"方案（${preset.server_count} 个 Server）？\n重复的 Server 会自动跳过。`)) return
    setImporting(prev => new Set([...prev, preset.id]))
    try {
      const r: any = await apiPost(`/presets/${preset.id}/import`)
      if (r.success) {
        setMessageType('success')
        setMessage(`已将 ${r.data?.imported || 0} 个 Server 加入你的追踪列表；重复项已跳过`)
        await load()
      } else {
        setMessageType('error')
        setMessage(typeof r.error === 'string' ? r.error : '导入失败')
      }
    } catch (error) {
      setMessageType('error')
      setMessage(error instanceof ApiRequestError && error.status === 401 ? '登录状态已失效，请重新登录' : '导入失败，请稍后重试')
    }
    finally { setImporting(prev => { const n = new Set(prev); n.delete(preset.id); return n }) }
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">📋 配置方案市场</h1>
          <p className="text-sm text-gray-500 mt-1">浏览他人分享的方案，将其中的 Server 加入你的 Hub 追踪列表；不会自动安装或启动本地进程。</p>
        </div>
        {!token || !userId ? (
          <Link to="/login" className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
            登录后发布
          </Link>
        ) : (
          <button onClick={() => setShowCreate(!showCreate)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
            {showCreate ? '取消' : '+ 发布方案'}
          </button>
        )}
      </div>

      {/* 创建表单 */}
      {showCreate && (
        <div className="bg-white rounded-xl border border-blue-200 p-5 space-y-3">
          <h3 className="font-semibold text-gray-900">发布我的配置方案</h3>
          <p className="text-xs text-gray-500">将你当前账户中追踪的 Server 发布为方案；导入者会建立自己的追踪记录。</p>
          <input type="text" value={newName} onChange={e => setNewName(e.target.value)}
            placeholder="方案名称（如：全栈 Web 开发方案）" className="w-full px-3 py-2 border rounded-lg text-sm" />
          <textarea value={newDesc} onChange={e => setNewDesc(e.target.value)} rows={2}
            placeholder="描述这个方案包含哪些功能..." className="w-full px-3 py-2 border rounded-lg text-sm" />
          <input type="text" value={newTags} onChange={e => setNewTags(e.target.value)}
            placeholder="标签（逗号分隔）：web, database, browser" className="w-full px-3 py-2 border rounded-lg text-sm" />
          <button onClick={handleCreate} disabled={creating}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {creating ? '发布中...' : '📤 发布方案'}
          </button>
        </div>
      )}

      {message && (
        <div className={`p-2 rounded-lg text-sm ${messageType === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`} role="status">
          {message}
        </div>
      )}

      {/* 排序 */}
      <div className="flex gap-2">
        {[
          ['hot', '🔥 热门'],
          ['new', '🆕 最新'],
          ['rating', '⭐ 评分'],
        ].map(([val, label]) => (
          <button key={val} onClick={() => setSort(val)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium ${sort === val ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {label}
          </button>
        ))}
      </div>

      {/* 方案列表 */}
      {loadError ? (
        <div className="text-center py-16 text-red-600">
          <p>{loadError}</p>
          <button onClick={load} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
        </div>
      ) : presets.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p>还没有配置方案</p>
          <p className="text-sm mt-1">成为第一个分享配置方案的人！</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {presets.map(p => (
            <div key={p.id} className="bg-white rounded-xl border border-gray-200 p-5 hover:border-blue-200 transition-colors">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <h3 className="font-semibold text-gray-900">{p.name}</h3>
                  <p className="text-xs text-gray-400">by {p.user_id} · {p.created_at?.slice(0, 10)}</p>
                </div>
                <span className="text-xs bg-blue-50 text-blue-600 px-2 py-0.5 rounded-full">{p.server_count} 个 Server</span>
              </div>
              {p.description && <p className="text-sm text-gray-500 mb-3">{p.description.slice(0, 100)}</p>}
              {(p.tags || []).length > 0 && (
                <div className="flex flex-wrap gap-1 mb-3">
                  {(p.tags || []).map(t => (
                    <span key={t} className="text-xs px-1.5 py-0.5 bg-gray-100 text-gray-500 rounded">{t}</span>
                  ))}
                </div>
              )}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span>📥 {p.download_count}</span>
                  <span>⭐ {p.rating || '-'}</span>
                </div>
                <button onClick={() => handleImport(p)} disabled={importing.has(p.id)}
                  className="px-4 py-1.5 bg-green-600 text-white rounded-lg text-xs font-medium hover:bg-green-700 disabled:opacity-50">
                  {importing.has(p.id) ? '导入中...' : '📥 一键导入'}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
