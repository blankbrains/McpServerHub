import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../../api/client'

function fmtNum(value: number | undefined): string {
  const n = Number(value || 0)
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

interface AdminOverviewData {
  stats: Record<string, number>
  daily_trend: Array<{ date: string; calls: number; tokens: number }>
  top_servers: Array<{ id: string; name: string; installs: number; calls_7d: number }>
  top_users: Array<{ user_id: string; display_name: string; calls_7d: number; tokens_7d: number }>
}

export default function AdminOverview() {
  const [data, setData] = useState<AdminOverviewData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    apiGet<AdminOverviewData>('/admin/overview')
      .then(result => {
        if (!cancelled) setData(result.data || null)
      })
      .catch(() => {
        if (!cancelled) {
          setData(null)
          setError('平台概览加载失败，请检查管理员权限后重试')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [reloadKey])

  if (loading) return <div role="status" className="py-16 text-center text-sm text-gray-400">正在加载平台数据...</div>
  if (error || !data) {
    return (
      <div role="alert" className="py-16 text-center text-red-600">
        <p>{error || '无法加载平台概览'}</p>
        <button type="button" onClick={() => setReloadKey(value => value + 1)} className="mt-3 text-sm text-blue-600 hover:underline">重试</button>
      </div>
    )
  }

  const { stats, daily_trend: trend, top_servers: topServers, top_users: topUsers } = data
  const maxCalls = Math.max(...trend.map(point => point.calls), 1)
  const maxTokens = Math.max(...trend.map(point => point.tokens), 1)

  return (
    <div className="max-w-6xl space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">MCP SERVER HUB / CONTROL ROOM</p>
          <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">📊 平台概览</h1>
          <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">查看用户、设备、Gateway 和中心 Hub 遥测的整体状态。</p>
        </div>
        <button type="button" onClick={() => setReloadKey(value => value + 1)} className="rounded-md border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800">
          刷新数据
        </button>
      </header>

      <section aria-label="平台核心指标" className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="总用户" value={fmtNum(stats.total_users)} tone="blue" hint="平台注册账号总数" />
        <Metric label="7 日活跃用户" value={fmtNum(stats.active_users_7d)} tone="indigo" hint="过去 7 天产生真实 Gateway 调用" />
        <Metric label="设备总数" value={fmtNum(stats.total_devices)} tone="purple" hint="用户创建的本地 Agent 设备" />
        <Metric label="在线 Gateway" value={fmtNum(stats.online_devices)} tone="green" hint="最近 3 分钟内有心跳或事件上报" />
        <Metric label="已完成接入" value={fmtNum(stats.connected_devices)} tone="cyan" hint="至少完成过一次 Gateway 接入" />
        <Metric label="平台 Server" value={fmtNum(stats.total_servers)} tone="slate" hint="中心 Hub 当前收录的全部 Server" />
        <Metric label="累计调用" value={fmtNum(stats.total_calls)} tone="orange" hint="统一活动口径下的工具调用" />
        <Metric label="累计估算 Token" value={fmtNum(stats.total_tokens)} tone="red" hint="Gateway 本地估算，不等同于模型账单" />
      </section>

      <section className="border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="font-semibold text-gray-900 dark:text-white">📈 Gateway 调用趋势</h2>
            <p className="mt-1 text-xs text-gray-500 dark:text-gray-400">最近 30 天的真实工具调用，普通对话不会进入这里。</p>
          </div>
          <span className="text-xs text-gray-400">数据口径：telemetry_events</span>
        </div>
        {trend.length > 0 ? (
          <>
            <div className="mt-5 flex h-44 items-end gap-1">
              {trend.map(point => (
                <div key={point.date} className="group flex h-full flex-1 items-end" title={`${point.date}: ${point.calls} 次调用，${fmtNum(point.tokens)} Token`}>
                  <div className="w-full rounded-t-sm bg-blue-500 transition-opacity group-hover:opacity-70 dark:bg-blue-400" style={{ height: `${Math.max((point.calls / maxCalls) * 100, 3)}%` }} />
                </div>
              ))}
            </div>
            <div className="mt-2 flex justify-between text-[10px] text-gray-400">
              <span>{trend[0]?.date}</span>
              <span>{trend[trend.length - 1]?.date}</span>
            </div>
            <div className="mt-3 flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
              <span><i className="mr-1 inline-block h-2 w-2 bg-blue-500" />调用次数</span>
              <span>峰值 Token：{fmtNum(maxTokens)}</span>
            </div>
          </>
        ) : (
          <div className="py-12 text-center text-sm text-gray-400">暂无 Gateway 调用数据</div>
        )}
      </section>

      <section className="grid min-w-0 gap-4 md:grid-cols-2">
        <RankPanel title="🏆 活跃 Server" link="/admin/servers" linkText="查看全部">
          {topServers.length > 0 ? topServers.map((server, index) => (
            <Link key={server.id} to={`/admin/servers/${encodeURIComponent(server.id)}`} className="flex min-w-0 items-center justify-between gap-3 border-b border-gray-100 py-2.5 text-sm last:border-0 dark:border-gray-700">
              <span className="min-w-0 flex-1 truncate text-gray-700 dark:text-gray-300" title={server.name || server.id}>{index + 1}. {server.name || server.id}</span>
              <span className="shrink-0 text-xs text-gray-400">追踪 {server.installs} · 调用 {fmtNum(server.calls_7d)}</span>
            </Link>
          )) : <Empty text="暂无 Server 活跃数据" />}
        </RankPanel>
        <RankPanel title="👥 活跃用户" link="/admin/users" linkText="查看设备">
          {topUsers.length > 0 ? topUsers.map((user, index) => (
            <Link key={user.user_id} to={`/admin/users/${encodeURIComponent(user.user_id)}`} className="flex min-w-0 items-center justify-between gap-3 border-b border-gray-100 py-2.5 text-sm last:border-0 dark:border-gray-700">
              <span className="min-w-0 flex-1 truncate text-gray-700 dark:text-gray-300" title={user.display_name || user.user_id}>{index + 1}. {user.display_name || user.user_id}</span>
              <span className="shrink-0 text-xs text-gray-400">📞 {fmtNum(user.calls_7d)} · 🔤 {fmtNum(user.tokens_7d)}</span>
            </Link>
          )) : <Empty text="暂无活跃用户数据" />}
        </RankPanel>
      </section>

      <section className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <QuickLink to="/admin/users" icon="👥" title="用户与设备" description="查看账号、设备、在线 Gateway 和首次调用状态。" />
        <QuickLink to="/admin/analytics" icon="📈" title="平台分析" description="按时间、用户和 Server 分析平台遥测。" />
        <QuickLink to="/admin/validation" icon="✅" title="接入验证" description="观察用户从创建设备到首次调用的完成情况。" />
        <QuickLink to="/admin/reviews" icon="🛡️" title="内容审核" description="处理用户评价；Server 安全等级和上下架在 Server 详情中完成。" />
      </section>
    </div>
  )
}

function Metric({ label, value, hint, tone }: { label: string; value: string; hint: string; tone: string }) {
  const tones: Record<string, string> = {
    blue: 'border-blue-200 bg-blue-50 dark:bg-blue-900/20',
    indigo: 'border-indigo-200 bg-indigo-50 dark:bg-indigo-900/20',
    purple: 'border-purple-200 bg-purple-50 dark:bg-purple-900/20',
    green: 'border-green-200 bg-green-50 dark:bg-green-900/20',
    cyan: 'border-cyan-200 bg-cyan-50 dark:bg-cyan-900/20',
    slate: 'border-slate-200 bg-slate-50 dark:bg-slate-900/20',
    orange: 'border-orange-200 bg-orange-50 dark:bg-orange-900/20',
    red: 'border-red-200 bg-red-50 dark:bg-red-900/20',
  }
  return (
    <div className={`border p-4 ${tones[tone] || tones.blue}`} title={hint}>
      <p className="text-2xl font-bold text-gray-900 dark:text-white">{value}</p>
      <p className="mt-1 text-xs font-medium text-gray-600 dark:text-gray-300">{label}</p>
      <p className="mt-1 text-[11px] leading-4 text-gray-400">{hint}</p>
    </div>
  )
}

function RankPanel({ title, link, linkText, children }: { title: string; link: string; linkText: string; children: ReactNode }) {
  return (
    <section className="min-w-0 border border-gray-200 bg-white p-5 dark:border-gray-700 dark:bg-gray-800">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h2 className="font-semibold text-gray-900 dark:text-white">{title}</h2>
        <Link to={link} className="text-xs text-blue-600 hover:underline">{linkText}</Link>
      </div>
      {children}
    </section>
  )
}

function QuickLink({ to, icon, title, description }: { to: string; icon: string; title: string; description: string }) {
  return (
    <Link to={to} className="border border-gray-200 bg-white p-4 transition-colors hover:border-blue-300 hover:bg-blue-50/40 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-blue-700 dark:hover:bg-blue-900/10">
      <span className="text-xl">{icon}</span>
      <h2 className="mt-2 text-sm font-semibold text-gray-900 dark:text-white">{title}</h2>
      <p className="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">{description}</p>
    </Link>
  )
}

function Empty({ text }: { text: string }) {
  return <p className="py-6 text-sm text-gray-400">{text}</p>
}
