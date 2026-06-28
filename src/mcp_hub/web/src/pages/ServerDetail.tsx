import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getServer, installServer, startServer, stopServer, rateServer, favoriteServer, ServerInfo } from '../api/client'
import StatusBadge from '../components/StatusBadge'

export default function ServerDetail() {
  const { id } = useParams<{ id: string }>()
  const [server, setServer] = useState<ServerInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [myRating, setMyRating] = useState(0)

  useEffect(() => {
    if (!id) return
    getServer(decodeURIComponent(id))
      .then(setServer)
      .catch(() => setMessage('加载失败'))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (!server) return <div className="text-center py-16 text-gray-400">Server 未找到</div>

  const handleInstall = async () => {
    const r = await installServer(server.id)
    setMessage(r.message || r.data?.detail || '安装完成')
    if (r.success) setServer({ ...server, status: 'stopped' })
  }

  const handleStart = async () => {
    const r = await startServer(server.id)
    setMessage(r.message || '已启动')
    if (r.success) setServer({ ...server, status: 'running' })
  }

  const handleStop = async () => {
    const r = await stopServer(server.id)
    setMessage(r.message || '已停止')
    if (r.success) setServer({ ...server, status: 'stopped' })
  }

  const handleRate = async (rating: number) => {
    await rateServer(server.id, rating)
    setMyRating(rating)
    setMessage(`评分 ${rating}⭐ 成功`)
  }

  const handleFavorite = async () => {
    const r = await favoriteServer(server.id)
    setMessage(r.favorited ? '已收藏' : '已取消收藏')
  }

  const stars = '⭐'.repeat(Math.round(server.rating))
  const securityLabels: Record<string, string> = {
    verified: '🔒 安全认证 - 经过官方安全审计',
    reviewed: '⚪ 已审查 - 自动扫描无已知风险',
    unreviewed: '⚠️ 未审查 - 请自行评估风险',
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">← 返回市场</Link>

      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{server.id}</h1>
            <p className="text-sm text-gray-400 mt-1">v{server.version || '?'}</p>
          </div>
          <StatusBadge status={server.status} />
        </div>

        <p className="text-gray-600 mb-4">{server.description || '暂无描述'}</p>

        <div className="flex items-center gap-4 text-sm text-gray-500 mb-4">
          <span>{stars} {server.rating}</span>
          <span>💬 {server.review_count} 评价</span>
          <span>📥 {server.download_count} 次下载</span>
          <span>📄 {server.license}</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap mb-4">
          {server.categories?.map((cat) => (
            <span key={cat} className="px-2.5 py-1 bg-blue-50 text-blue-600 rounded text-xs font-medium">{cat}</span>
          ))}
          {server.tags?.map((tag) => (
            <span key={tag} className="px-2.5 py-1 bg-gray-50 text-gray-500 rounded text-xs">{tag}</span>
          ))}
        </div>

        <p className="text-sm text-gray-500 mb-4">{securityLabels[server.security_level] || server.security_level}</p>

        {/* Actions */}
        <div className="flex items-center gap-3 flex-wrap">
          {server.status === 'not_installed' && (
            <button onClick={handleInstall} className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors">
              📥 一键安装
            </button>
          )}
          {server.status === 'stopped' && (
            <button onClick={handleStart} className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium transition-colors">
              ▶️ 启动
            </button>
          )}
          {server.status === 'running' && (
            <button onClick={handleStop} className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium transition-colors">
              ⏹ 停止
            </button>
          )}
          <button onClick={handleFavorite} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            ⭐ 收藏
          </button>
          {server.homepage && (
            <a href={server.homepage} target="_blank" rel="noopener noreferrer" className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm">
              🔗 GitHub
            </a>
          )}
        </div>

        {message && (
          <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">{message}</div>
        )}
      </div>

      {/* Rating */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-3">评分</h2>
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              onClick={() => handleRate(n)}
              className={`text-2xl transition-colors ${n <= (myRating || Math.round(server.rating)) ? '' : 'grayscale opacity-40'}`}
            >
              ⭐
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
