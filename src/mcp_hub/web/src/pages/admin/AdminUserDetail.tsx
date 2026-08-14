import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { apiGet, apiPatch } from '../../api/client'
import { useAuthState } from '../../hooks/useAuthState'

export default function AdminUserDetail() {
  const { userId } = useParams<{ userId: string }>()
  const currentUserId = useAuthState().userId
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const [savingRole, setSavingRole] = useState(false)

  const load = async () => {
    if (!userId) return
    setLoading(true)
    setError('')
    try {
      const result = await apiGet<any>(`/admin/users/${encodeURIComponent(userId)}`)
      setData(result.data || null)
    } catch {
      setData(null)
      setError('用户详情加载失败，请检查管理员权限后重试')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [userId])

  const changeRole = async (newRole: string) => {
    if (!window.confirm(`确定将角色修改为 ${newRole}？`)) return
    setSavingRole(true)
    try {
      const r: any = await apiPatch(`/admin/users/${encodeURIComponent(userId!)}/role`, { role: newRole })
      setMsg(r.success ? `✅ ${r.message}` : `❌ ${r.error || r.message}`)
      if (r.success && data) setData({ ...data, profile: { ...data.profile, role: newRole } })
    } catch { setMsg('❌ 操作失败') }
    finally { setSavingRole(false) }
    setTimeout(() => setMsg(''), 3000)
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (error || !data) return (
    <div className="text-center py-16 text-red-600">
      <p>{error || '用户不存在'}</p>
      <button onClick={load} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
    </div>
  )

  const { profile, stats, devices = [], servers, daily_trend, top_tools } = data
  const maxCalls = Math.max(...daily_trend.map((d: any) => d.calls), 1)

  return (
    <div className="max-w-5xl space-y-5">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">OPERATIONS / USER DETAIL</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">👤 用户详情</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">查看账号使用情况、设备接入和 Gateway 运行状态。</p>
      </header>
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
                <button onClick={() => changeRole('admin')} disabled={savingRole} className="text-xs text-blue-600 hover:text-blue-800 disabled:opacity-50">提升为管理员</button>
              ) : profile.id === currentUserId ? (
                <span className="text-xs text-gray-400">当前登录账号不可自我降级</span>
              ) : (
                <button onClick={() => changeRole('user')} disabled={savingRole} className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50">降级为用户</button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        {[
          ['追踪 Server', stats.server_count],
          ['总调用', stats.total_calls >= 1000 ? `${(stats.total_calls / 1000).toFixed(1)}K` : stats.total_calls],
          ['总估算 Token', stats.total_tokens >= 1000 ? `${(stats.total_tokens / 1000).toFixed(1)}K` : stats.total_tokens],
          ['收藏', stats.favorite_count],
          ['设备', stats.device_count],
          ['在线 Gateway', stats.online_device_count],
        ].map(([l, v]) => (
          <div key={l as string} className="bg-white dark:bg-gray-800 rounded-xl border p-3 text-center">
            <p className="text-xl font-bold text-gray-900 dark:text-white">{v}</p>
            <p className="text-xs text-gray-500">{l}</p>
          </div>
        ))}
      </div>

      <section className="border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">🖥️ 本地 Agent 设备</h2>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">设备令牌归属于该账号；管理员只能查看接入状态，不能读取用户电脑配置或令牌。</p>
          </div>
          <span className="text-xs text-gray-400">{stats.online_device_count || 0} 台在线 / {devices.length} 台总计</span>
        </div>
        {devices.length === 0 ? (
          <p className="py-8 text-sm text-gray-400">该用户尚未创建设备。</p>
        ) : (
          <div className="mt-4 divide-y divide-gray-100 dark:divide-gray-700">
            {devices.map((device: any) => (
              <div key={device.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`h-2 w-2 rounded-full ${device.online ? 'bg-green-500' : device.revoked ? 'bg-red-500' : 'bg-gray-300'}`} />
                    <p className="truncate text-sm font-medium text-gray-800 dark:text-gray-200">{device.name}</p>
                    <span className="text-xs text-gray-400">{device.agent_type}</span>
                  </div>
                  <p className="mt-1 text-xs text-gray-400">
                    Gateway {device.gateway_version || '-'} · {device.platform || 'unknown'} · {device.server_count || 0} 个 Server
                  </p>
                </div>
                <div className="text-right text-xs text-gray-400">
                  <p className={device.online ? 'font-medium text-green-600' : device.revoked ? 'text-red-500' : 'text-gray-500'}>
                    {device.revoked ? '已撤销' : device.online ? '在线' : device.connected ? '已接入，当前离线' : '未完成接入'}
                  </p>
                  <p className="mt-1">最后心跳：{device.last_seen_at ? device.last_seen_at.slice(0, 16) : '尚无'}</p>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

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
        <h3 className="font-semibold text-gray-900 dark:text-white mb-3">📦 已追踪 Server（{servers.length}）</h3>
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
