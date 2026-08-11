import { useState, useEffect } from 'react'
import { apiGet } from '../../api/client'

export default function AdminAnalytics() {
  const [days, setDays] = useState(7)
  const [trend, setTrend] = useState<any[]>([])
  const [topServers, setTopServers] = useState<any[]>([])
  const [topUsers, setTopUsers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    setLoading(true)
    setError(null)
    Promise.all([
      apiGet<any[]>(`/admin/analytics/daily?days=${days}`),
      apiGet<any[]>(`/admin/analytics/top-servers?days=${days}`),
      apiGet<any[]>(`/admin/analytics/top-users?days=${days}`),
    ]).then(([t, s, u]) => {
      setTrend(t?.data || [])
      setTopServers(s?.data || [])
      setTopUsers(u?.data || [])
    }).catch(() => {
      setError('加载分析数据失败')
    }).finally(() => setLoading(false))
  }, [days, reloadKey])

  const maxCalls = Math.max(...trend.map((d: any) => d.calls), 1)

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  if (error) return (
    <div className="text-center py-16">
      <p className="text-red-500 mb-4">{error}</p>
      <button onClick={() => setReloadKey(value => value + 1)} className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">重试</button>
    </div>
  )

  return (
    <div className="max-w-6xl space-y-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">📈 使用分析</h1>
        <div className="flex gap-1">
          {[7, 14, 30].map(d => (
            <button key={d} onClick={() => setDays(d)} className={`px-3 py-1.5 rounded-lg text-xs font-medium ${days === d ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-700 dark:text-gray-300'}`}>{d} 天</button>
          ))}
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h2 className="font-semibold text-gray-900 dark:text-white mb-3">每日调用 + 估算 Token 趋势</h2>
        <div className="flex items-end gap-1 h-44">
          {trend.map((d: any) => (
            <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full" title={`${d.date}: ${d.calls} 调用, ${d.tokens} 估算 Token, ${d.active_users} 用户`}>
              <div className="w-full bg-blue-500 dark:bg-blue-400 rounded-t-sm" style={{ height: `${Math.max((d.calls / maxCalls) * 100, 2)}%`, opacity: 0.4 + (d.tokens / Math.max(...trend.map((x: any) => x.tokens), 1)) * 0.6 }} />
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl border p-5">
          <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">🏆 Top Server</h3>
          <div className="space-y-1.5">
            {topServers.map((s: any, i: number) => (
              <div key={s.server_id} className="flex justify-between text-sm py-1">
                <span className="text-gray-700 dark:text-gray-300">{i + 1}. {s.name || s.server_id}</span>
                <span className="text-xs text-gray-400">📞 {s.calls} · 🔤 {s.tokens >= 1000 ? `${(s.tokens/1000).toFixed(1)}K` : s.tokens}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl border p-5">
          <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">👥 Top 用户</h3>
          <div className="space-y-1.5">
            {topUsers.map((u: any, i: number) => (
              <div key={u.user_id} className="flex justify-between text-sm py-1">
                <span className="text-gray-700 dark:text-gray-300">{i + 1}. {u.display_name || u.user_id}</span>
                <span className="text-xs text-gray-400">📞 {u.calls} · 🔤 {u.tokens >= 1000 ? `${(u.tokens/1000).toFixed(1)}K` : u.tokens}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
