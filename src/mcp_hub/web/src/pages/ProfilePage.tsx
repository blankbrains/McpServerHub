import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getAuthState, apiGet } from '../api/client'

interface UserProfile {
  id: string
  display_name: string
  avatar_url: string
  email: string
  role: string
  created_at: string
  last_login: string
}

interface ServerStat {
  server_id: string
  name: string
  status: string
  call_count_7d: number
  token_consumption: number
}

function fmtNum(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

export default function ProfilePage() {
  const { userId, token } = getAuthState()
  const [profile, setProfile] = useState<UserProfile | null>(null)
  const [servers, setServers] = useState<ServerStat[]>([])
  const [usageSummary, setUsageSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')

  useEffect(() => {
    async function load() {
      try {
        // 加载用户信息
        let gotProfile = false
        if (token) {
          try {
            const me = await apiGet<any>('/auth/me')
            if (me.data) { setProfile(me.data); gotProfile = true }
          } catch {}
        }

        // API 未返回时用 localStorage 构建基本用户信息
        if (!gotProfile && userId) {
          setProfile({
            id: userId,
            display_name: userId,
            avatar_url: '',
            email: '',
            role: 'user',
            created_at: '',
            last_login: '',
          })
        }

        // 加载用户的 Server 列表
        const sr = await apiGet<any>('/monitor/dashboard')
        if (sr.data?.servers) {
          const userServers = sr.data.servers.filter((s: any) =>
            s.status !== 'not_installed' || s.enabled !== false
          )
          setServers(userServers.slice(0, 20))
        }

        // 加载使用统计
        if (userId) {
          try {
            const us = await fetch(`/api/v1/usage/stats?user_id=${encodeURIComponent(userId)}&days=30`, {
              headers: { 'x-user-id': userId },
            }).then(r => r.json())
            if (us.data) setUsageSummary(us.data)
          } catch {}
        }
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [userId, token])

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  // 计算汇总
  const totalCalls = usageSummary?.stats?.reduce((sum: number, s: any) => sum + (s.total_calls || 0), 0) || 0
  const totalTokens = usageSummary?.stats?.reduce((sum: number, s: any) => sum + (s.total_tokens || 0), 0) || 0
  const totalErrors = usageSummary?.stats?.reduce((sum: number, s: any) => sum + (s.error_count || 0), 0) || 0
  const successRate = totalCalls > 0 ? Math.round((totalCalls - totalErrors) / totalCalls * 100) : 100

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">👤 个人中心</h1>

      {/* 用户信息卡片 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-4">
          {profile?.avatar_url ? (
            <img src={profile.avatar_url} alt="" className="w-16 h-16 rounded-full" />
          ) : (
            <div className="w-16 h-16 rounded-full bg-blue-600 flex items-center justify-center text-white text-2xl font-bold">
              {(profile?.display_name || profile?.id || '?')[0].toUpperCase()}
            </div>
          )}
          <div>
            <h2 className="text-xl font-bold text-gray-900">{profile?.display_name || profile?.id || '未登录'}</h2>
            <div className="flex items-center gap-3 text-sm text-gray-500 mt-1">
              {profile?.id && <span>@{profile.id}</span>}
              {profile?.email && <span>📧 {profile.email}</span>}
              {profile?.role && (
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                  profile.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'
                }`}>
                  {profile.role === 'admin' ? '🛡️ 管理员' : '👤 用户'}
                </span>
              )}
            </div>
            <div className="flex gap-4 text-xs text-gray-400 mt-2">
              {profile?.created_at && <span>注册于 {profile.created_at.slice(0, 10)}</span>}
              {profile?.last_login && <span>最后登录 {profile.last_login.slice(0, 10)}</span>}
            </div>
          </div>
        </div>
      </div>

      {/* 使用统计卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon="📦" label="我的 Server" value={String(servers.length)} color="blue" />
        <StatCard icon="📞" label="30 日调用" value={fmtNum(totalCalls)} color="green" />
        <StatCard icon="🔤" label="30 日 Token" value={fmtNum(totalTokens)} color="purple" />
        <StatCard icon="✅" label="成功率" value={`${successRate}%`} color={successRate >= 95 ? 'green' : 'yellow'} />
      </div>

      {/* 使用趋势概览 */}
      {usageSummary?.stats && usageSummary.stats.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">📊 30 日使用趋势</h2>
          <div className="space-y-3">
            {usageSummary.stats.slice(0, 6).map((s: any, i: number) => {
              const maxCalls = Math.max(...usageSummary.stats.map((x: any) => x.total_calls || 0), 1)
              const pct = Math.round((s.total_calls || 0) / maxCalls * 100)
              return (
                <div key={s.server_id} className="flex items-center gap-3">
                  <span className="text-xs text-gray-500 w-28 truncate flex-shrink-0" title={s.server_id}>
                    {s.server_id.split('/').pop()}
                  </span>
                  <div className="flex-1 bg-gray-100 rounded-full h-5 relative overflow-hidden">
                    <div
                      className="h-full rounded-full transition-all duration-500 flex items-center justify-end pr-2"
                      style={{
                        width: `${Math.max(pct, 4)}%`,
                        backgroundColor: i === 0 ? '#3B82F6' : i === 1 ? '#8B5CF6' : i === 2 ? '#10B981' : '#6B7280',
                      }}
                    >
                      <span className="text-[10px] text-white font-medium">{fmtNum(s.total_calls)} 次</span>
                    </div>
                  </div>
                  <span className="text-xs text-gray-400 w-16 text-right flex-shrink-0">
                    {s.success_rate || 0}% 成功
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 我的 Server 列表 */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">📦 我的 Server（{servers.length}）</h2>
          <Link to="/my-servers" className="text-sm text-blue-600 hover:text-blue-800">管理 →</Link>
        </div>
        {servers.length === 0 ? (
          <p className="text-sm text-gray-400 text-center py-8">还没有安装任何 Server，去市场看看吧</p>
        ) : (
          <div className="space-y-2">
            {servers.slice(0, 8).map(s => (
              <div key={s.server_id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <Link to={`/servers/${encodeURIComponent(s.server_id)}`}
                  className="text-sm font-medium text-gray-800 hover:text-blue-600 truncate">
                  {s.name || s.server_id}
                </Link>
                <div className="flex items-center gap-3 text-xs text-gray-400">
                  <span>📞 {fmtNum(s.call_count_7d || 0)}</span>
                  <span>🔤 {fmtNum(s.token_consumption || 0)}</span>
                </div>
              </div>
            ))}
            {servers.length > 8 && (
              <p className="text-xs text-gray-400 text-center">还有 {servers.length - 8} 个 Server</p>
            )}
          </div>
        )}
      </div>

      {/* 使用详情（按 Server 分组） */}
      {usageSummary?.stats && usageSummary.stats.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">📊 30 日使用详情</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-gray-400 border-b">
                  <th className="pb-2 font-medium">Server</th>
                  <th className="pb-2 font-medium text-right">调用次数</th>
                  <th className="pb-2 font-medium text-right">Token 消耗</th>
                  <th className="pb-2 font-medium text-right">平均耗时</th>
                  <th className="pb-2 font-medium text-right">成功率</th>
                </tr>
              </thead>
              <tbody>
                {usageSummary.stats.map((s: any) => (
                  <tr key={s.server_id} className="border-b border-gray-50">
                    <td className="py-2 text-gray-800">{s.server_id.split('/').pop()}</td>
                    <td className="py-2 text-right text-gray-600">{fmtNum(s.total_calls)}</td>
                    <td className="py-2 text-right text-gray-600">{fmtNum(s.total_tokens)}</td>
                    <td className="py-2 text-right text-gray-400">{s.avg_duration_ms}ms</td>
                    <td className="py-2 text-right">
                      <span className={s.success_rate >= 95 ? 'text-green-600' : s.success_rate >= 80 ? 'text-yellow-600' : 'text-red-600'}>
                        {s.success_rate}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 快捷入口 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Link to="/my-config" className="flex items-center gap-2 p-3 bg-white rounded-xl border border-gray-200 hover:border-blue-300 transition-colors text-sm text-gray-700">
          ⚙️ 配置管理
        </Link>
        <Link to="/market" className="flex items-center gap-2 p-3 bg-white rounded-xl border border-gray-200 hover:border-blue-300 transition-colors text-sm text-gray-700">
          🏪 浏览市场
        </Link>
        <Link to="/monitor" className="flex items-center gap-2 p-3 bg-white rounded-xl border border-gray-200 hover:border-blue-300 transition-colors text-sm text-gray-700">
          📈 监控大屏
        </Link>
        <Link to="/guide" className="flex items-center gap-2 p-3 bg-white rounded-xl border border-gray-200 hover:border-blue-300 transition-colors text-sm text-gray-700">
          📖 使用指南
        </Link>
      </div>
    </div>
  )
}

function StatCard({ icon, label, value, color }: { icon: string; label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    green: 'bg-green-50 border-green-200',
    blue: 'bg-blue-50 border-blue-200',
    purple: 'bg-purple-50 border-purple-200',
    yellow: 'bg-yellow-50 border-yellow-200',
  }
  return (
    <div className={`rounded-xl border p-4 ${colors[color] || colors.blue}`}>
      <div className="flex items-center gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
          <p className="text-sm text-gray-500">{label}</p>
        </div>
      </div>
    </div>
  )
}
