import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getAuthState } from '../api/client'

interface NotifItem {
  id: number
  type: string
  title: string
  message: string
  server_id: string
  link: string
  is_read: boolean
  created_at: string
}

const typeConfig: Record<string, { icon: string; label: string; color: string }> = {
  alert: { icon: '🚨', label: '告警', color: 'bg-red-50 border-red-200' },
  update: { icon: '🆕', label: '更新', color: 'bg-blue-50 border-blue-200' },
  reply: { icon: '💬', label: '回复', color: 'bg-green-50 border-green-200' },
  system: { icon: '📢', label: '系统', color: 'bg-purple-50 border-purple-200' },
}

export default function NotificationsPage() {
  const [items, setItems] = useState<NotifItem[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const userId = getAuthState().userId || 'anonymous'

  const load = async () => {
    try {
      const r = await fetch(`/api/v1/notifications?page_size=50`, {
        headers: { 'x-user-id': userId },
      }).then(r => r.json())
      if (r.data) {
        setItems(r.data.items)
        setUnreadCount(r.data.unread_count)
      }
    } catch { setError('加载通知失败') }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const markRead = async (id: number) => {
    const prevItems = items
    const prevCount = unreadCount
    setItems(prev => prev.map(i => i.id === id ? { ...i, is_read: true } : i))
    setUnreadCount(c => Math.max(0, c - 1))
    try {
      await fetch(`/api/v1/notifications/${id}/read`, {
        method: 'POST', headers: { 'x-user-id': userId },
      })
    } catch {
      setItems(prevItems)
      setUnreadCount(prevCount)
      setError('标记失败')
    }
  }

  const markAllRead = async () => {
    const prevItems = items
    setItems(prev => prev.map(i => ({ ...i, is_read: true })))
    setUnreadCount(0)
    try {
      await fetch('/api/v1/notifications/read-all', {
        method: 'POST', headers: { 'x-user-id': userId },
      })
    } catch {
      setItems(prevItems)
      setUnreadCount(prevItems.filter(i => !i.is_read).length)
      setError('操作失败')
    }
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="max-w-3xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">🔔 通知中心</h1>
        {unreadCount > 0 && (
          <button onClick={markAllRead} className="text-sm text-blue-600 hover:text-blue-800">
            全部标为已读
          </button>
        )}
      </div>

      {error && (
        <div className="p-2 bg-red-50 text-red-700 rounded-lg text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={() => { setError(''); load() }} className="text-red-400 hover:text-red-600 ml-2">重试</button>
        </div>
      )}

      {items.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg">暂无通知</p>
          <p className="text-sm mt-1">当 Server 出现异常、有更新或收到回复时，通知会出现在这里</p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map(n => {
            const cfg = typeConfig[n.type] || { icon: '📌', label: n.type, color: 'bg-gray-50 border-gray-200' }
            return (
              <div key={n.id}
                className={`rounded-xl border p-4 transition-colors cursor-pointer ${n.is_read ? 'bg-white border-gray-200 opacity-70' : `${cfg.color} border-l-4 border-l-blue-500`}`}
                onClick={() => !n.is_read && markRead(n.id)}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-100">{cfg.icon} {cfg.label}</span>
                      {!n.is_read && <span className="w-2 h-2 rounded-full bg-blue-500 flex-shrink-0" />}
                    </div>
                    <p className="font-medium text-gray-900 text-sm">{n.title}</p>
                    {n.message && <p className="text-xs text-gray-500 mt-0.5">{n.message}</p>}
                    <p className="text-xs text-gray-400 mt-1">{n.created_at?.slice(0, 16) || ''}</p>
                  </div>
                  {n.link && (
                    <Link to={n.link} className="text-xs text-blue-600 hover:text-blue-800 flex-shrink-0">
                      查看 →
                    </Link>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
