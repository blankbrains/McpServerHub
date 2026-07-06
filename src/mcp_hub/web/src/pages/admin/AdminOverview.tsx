import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getAuthState } from '../../api/client'

function fmtNum(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

export default function AdminOverview() {
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const uid = getAuthState().userId || 'anonymous'

  useEffect(() => {
    fetch('/api/v1/admin/overview', { headers: { 'x-user-id': uid } })
      .then(r => r.json()).then(r => { if (r.data) setData(r.data) })
      .catch(() => {}).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (!data) return <div className="text-center py-16 text-gray-400">无法加载数据</div>

  const { stats, daily_trend, top_servers, top_users } = data
  const maxCalls = Math.max(...daily_trend.map((d: any) => d.calls), 1)

  return (
    <div className="max-w-6xl space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">📊 平台概览</h1>

      {/* 统计卡片 */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3">
        <Card label="总用户" value={fmtNum(stats.total_users)} color="blue" />
        <Card label="总 Server" value={fmtNum(stats.total_servers)} color="purple" />
        <Card label="总安装" value={fmtNum(stats.total_installs)} color="green" />
        <Card label="总调用" value={fmtNum(stats.total_calls)} color="orange" />
        <Card label="总 Token" value={fmtNum(stats.total_tokens)} color="red" />
        <Card label="7日活跃" value={fmtNum(stats.active_users_7d)} color="indigo" />
      </div>

      {/* 每日趋势 */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
        <h2 className="font-semibold text-gray-900 dark:text-white mb-3">📈 每日调用趋势（30 天）</h2>
        <div className="flex items-end gap-1 h-40">
          {daily_trend.map((d: any) => (
            <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full" title={`${d.date}: ${d.calls} 调用, ${fmtNum(d.tokens)} Token`}>
              <div className="w-full bg-blue-500 dark:bg-blue-400 rounded-t-sm transition-all"
                style={{ height: `${Math.max((d.calls / maxCalls) * 100, 2)}%`, opacity: 0.6 + (d.tokens / Math.max(...daily_trend.map((x: any) => x.tokens), 1)) * 0.4 }} />
            </div>
          ))}
        </div>
        <div className="flex justify-between text-[10px] text-gray-400 mt-1">
          <span>{daily_trend[0]?.date}</span>
          <span>{daily_trend[daily_trend.length - 1]?.date}</span>
        </div>
      </div>

      {/* Top 排行 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <h2 className="font-semibold text-gray-900 dark:text-white mb-3">🏆 Top Server</h2>
          <div className="space-y-2">
            {top_servers.map((s: any, i: number) => (
              <Link key={s.id} to={`/admin/servers/${encodeURIComponent(s.id)}`}
                className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-sm">
                <span className="text-gray-700 dark:text-gray-300 truncate">{i + 1}. {s.name || s.id}</span>
                <span className="text-xs text-gray-400 ml-2">📥 {s.installs} · 📞 {fmtNum(s.calls_7d)}</span>
              </Link>
            ))}
          </div>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-5">
          <h2 className="font-semibold text-gray-900 dark:text-white mb-3">👥 Top 用户</h2>
          <div className="space-y-2">
            {top_users.map((u: any, i: number) => (
              <Link key={u.user_id} to={`/admin/users/${encodeURIComponent(u.user_id)}`}
                className="flex items-center justify-between p-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 text-sm">
                <span className="text-gray-700 dark:text-gray-300 truncate">{i + 1}. {u.display_name || u.user_id}</span>
                <span className="text-xs text-gray-400 ml-2">📞 {fmtNum(u.calls_7d)}</span>
              </Link>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

function Card({ label, value, color }: { label: string; value: string; color: string }) {
  const colors: Record<string, string> = {
    blue: 'border-blue-200 bg-blue-50 dark:bg-blue-900/20', purple: 'border-purple-200 bg-purple-50 dark:bg-purple-900/20',
    green: 'border-green-200 bg-green-50 dark:bg-green-900/20', orange: 'border-orange-200 bg-orange-50 dark:bg-orange-900/20',
    red: 'border-red-200 bg-red-50 dark:bg-red-900/20', indigo: 'border-indigo-200 bg-indigo-50 dark:bg-indigo-900/20',
  }
  return (
    <div className={`rounded-xl border p-3 ${colors[color] || colors.blue}`}>
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
      <p className="text-xs text-gray-500 dark:text-gray-400">{label}</p>
    </div>
  )
}
