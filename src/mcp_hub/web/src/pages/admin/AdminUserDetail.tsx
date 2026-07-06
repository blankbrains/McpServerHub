import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { getAuthState } from '../../api/client'

export default function AdminUserDetail() {
  const { userId } = useParams<{ userId: string }>()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const uid = getAuthState().userId || 'anonymous'

  useEffect(() => {
    if (!userId) return
    fetch(`/api/v1/admin/users/${encodeURIComponent(userId)}`, { headers: { 'x-user-id': uid } })
      .then(r => r.json()).then(r => { if (r.data) setData(r.data) })
      .catch(() => {}).finally(() => setLoading(false))
  }, [userId])

  const changeRole = async (newRole: string) => {
    if (!window.confirm(`确定将角色修改为 ${newRole}？`)) return
    try {
      const r = await fetch(`/api/v1/admin/users/${encodeURIComponent(userId!)}/role`, {
        method: 'PATCH', headers: { 'Content-Type': 'application/json', 'x-user-id': uid },
        body: JSON.stringify({ role: newRole }),
      }).then(r => r.json())
      setMsg(r.success ? `✅ ${r.message}` : `❌ ${r.error || r.message}`)
      if (r.success && data) setData({ ...data, profile: { ...data.profile, role: newRole } })
    } catch { setMsg('❌ 操作失败') }
    setTimeout(() => setMsg(''), 3000)
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (!data) return <div className="text-center py-16 text-gray-400">用户不存在</div>

  const { profile, stats, servers, daily_trend, top_tools } = data
  const maxCalls = Math.max(...daily_trend.map((d: any) => d.calls), 1)

  return (
    <div className="max-w-4xl space-y-5">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">👤 用户详情</h1>
      {msg && <div className={`p-2 rounded-lg text-sm ${msg.startsWith('✅') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>{msg}</div>}

      {/* Profile */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <div className="flex items-center gap-4">
          {profile.avatar_url ? <img src={profile.avatar_url} className="w-14 h-14 rounded-full" alt="" /> : <div className="w-14 h-14 rounded-full bg-blue-500 flex items-center justify-center text-white text-xl font-bold">{profile.display_name?.[0]}</div>}
          <div>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white">{profile.display_name}</h2>
            <p className="text-sm text-gray-500">@{profile.id} · {profile.email || '无邮箱'} · 注册于 {profile.created_at?.slice(0, 10)}</p>
            <div className="flex items-center gap-2 mt-2">
              <span className={`text-xs px-2 py-0.5 rounded-full ${profile.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>{profile.role === 'admin' ? '🛡️ 管理员' : '👤 用户'}</span>
              {profile.role !== 'admin' ? (
                <button onClick={() => changeRole('admin')} className="text-xs text-blue-600 hover:text-blue-800">提升为管理员</button>
              ) : (
                <button onClick={() => changeRole('user')} className="text-xs text-red-500 hover:text-red-700">降级为用户</button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {[['Server', stats.server_count], ['总调用', stats.total_calls >= 1000 ? `${(stats.total_calls/1000).toFixed(1)}K` : stats.total_calls], ['总Token', stats.total_tokens >= 1000 ? `${(stats.total_tokens/1000).toFixed(1)}K` : stats.total_tokens], ['收藏', stats.favorite_count]].map(([l, v]) => (
          <div key={l as string} className="bg-white dark:bg-gray-800 rounded-xl border p-3 text-center">
            <p className="text-xl font-bold text-gray-900 dark:text-white">{v}</p>
            <p className="text-xs text-gray-500">{l}</p>
          </div>
        ))}
      </div>

      {/* Trend */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-white mb-3">📈 每日调用趋势</h3>
        <div className="flex items-end gap-1 h-32">
          {daily_trend.map((d: any) => (
            <div key={d.date} className="flex-1 bg-blue-500 dark:bg-blue-400 rounded-t-sm transition-all"
              style={{ height: `${Math.max((d.calls / maxCalls) * 100, 2)}%` }} title={`${d.date}: ${d.calls} 调用`} />
          ))}
        </div>
      </div>

      {/* Servers */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h3 className="font-semibold text-gray-900 dark:text-white mb-3">📦 安装的 Server（{servers.length}）</h3>
        <div className="space-y-1.5">
          {servers.map((s: any) => (
            <div key={s.server_id} className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm">
              <span className="text-gray-700 dark:text-gray-300">{s.name || s.server_id}</span>
              <div className="flex items-center gap-3 text-xs text-gray-400">
                <span>📞 {s.calls_7d}</span><span>🔤 {s.tokens_7d}</span>
                <span className={s.enabled ? 'text-green-500' : 'text-red-400'}>{s.enabled ? '启用' : '禁用'}</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Top Tools */}
      {top_tools.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <h3 className="font-semibold text-gray-900 dark:text-white mb-3">🔧 最常用工具</h3>
          <div className="space-y-1">
            {top_tools.map((t: any, i: number) => (
              <div key={t.tool_name} className="flex items-center gap-3 text-sm">
                <span className="text-gray-400 w-5">{i + 1}.</span>
                <span className="text-gray-700 dark:text-gray-300 flex-1">{t.tool_name}</span>
                <span className="text-gray-400 text-xs">{t.count} 次</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
