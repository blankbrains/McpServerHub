import { useState, useEffect } from 'react'
import { useParams } from 'react-router-dom'
import { apiGet, apiPost } from '../../api/client'

export default function AdminServerDetail() {
  const { serverId } = useParams<{ serverId: string }>()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [msg, setMsg] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async () => {
    if (!serverId) return
    setLoading(true)
    setError('')
    try {
      const result = await apiGet<any>(`/admin/servers/${encodeURIComponent(serverId)}`)
      setData(result.data || null)
    } catch {
      setData(null)
      setError('Server 详情加载失败，请检查管理员权限后重试')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [serverId])

  const updateServer = async (path: string, body: any) => {
    setSaving(true)
    try {
      const result: any = await apiPost(path, body)
      if (!result.success) throw new Error(result.error || result.message || '操作失败')
      setMsg(result.message || '操作成功')
      await load()
    } catch (requestError) {
      setMsg(requestError instanceof Error ? requestError.message : '操作失败')
    } finally {
      setSaving(false)
      setTimeout(() => setMsg(''), 3000)
    }
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (error || !data) return (
    <div className="text-center py-16 text-red-600">
      <p>{error || 'Server 不存在'}</p>
      <button onClick={load} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
    </div>
  )

  const { server, stats, install_users, daily_trend, top_tools } = data
  const maxCalls = Math.max(...daily_trend.map((d: any) => d.calls), 1)

  return (
    <div className="max-w-4xl space-y-5">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">📦 {server.name || server.server_id}</h1>
      {msg && <p className="p-3 text-sm rounded-lg bg-blue-50 text-blue-700">{msg}</p>}

      <div className="bg-white dark:bg-gray-800 rounded-xl border p-5">
        <p className="text-sm text-gray-500">{server.description}</p>
        <div className="flex flex-wrap gap-2 mt-2 items-center">
          <span className={`text-xs px-2 py-0.5 rounded-full ${server.security_level === 'blocked' ? 'bg-red-100 text-red-700' : server.security_level === 'verified' ? 'bg-green-100 text-green-700' : server.security_level === 'reviewed' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'}`}>安全: {server.security_level}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${server.market_visible ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
            市场：{server.market_visible ? '可见' : '已隐藏'}
          </span>
          {/* 管理操作 */}
          <button onClick={async () => {
            if (!window.confirm(server.security_level === 'blocked' ? '确定恢复此 Server？' : '确定下架此 Server？')) return
            const action = server.security_level === 'blocked' ? 'unblock' : 'block'
            await updateServer(`/admin/servers/${encodeURIComponent(server.server_id)}/toggle`, { action })
          }} disabled={saving} className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded hover:bg-red-100 disabled:opacity-50">
            {server.security_level === 'blocked' ? '恢复' : '下架'}
          </button>
          <select onChange={async (e) => {
            if (!e.target.value || !window.confirm(`确定将安全等级设为 ${e.target.value}？`)) return
            await updateServer(`/admin/servers/${encodeURIComponent(server.server_id)}/security`, { level: e.target.value })
          }} disabled={saving} className="text-xs px-2 py-1 border rounded bg-white dark:bg-gray-700 dark:text-white disabled:opacity-50">
            <option value="">调整安全等级</option>
            <option value="verified">🟢 安全认证</option>
            <option value="reviewed">🟡 已审查</option>
            <option value="unreviewed">🟠 未审查</option>
            <option value="blocked">🔴 已阻止</option>
          </select>
        </div>
        <div className="flex flex-wrap gap-2 mt-2">
          {server.categories?.map((c: string) => <span key={c} className="text-xs px-2 py-0.5 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded">{c}</span>)}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {[['追踪用户', stats.install_count], ['7日调用', stats.calls_7d], ['7日估算 Token', stats.tokens_7d >= 1000 ? `${(stats.tokens_7d/1000).toFixed(1)}K` : stats.tokens_7d], ['评分', `${server.rating?.toFixed(1) || '-'}⭐`]].map(([l, v]) => (
          <div key={l as string} className="bg-white dark:bg-gray-800 rounded-xl border p-3 text-center">
            <p className="text-xl font-bold text-gray-900 dark:text-white">{v}</p><p className="text-xs text-gray-500">{l}</p>
          </div>
        ))}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border p-5">
        <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">📈 每日调用趋势</h3>
        <div className="flex items-end gap-1 h-32">
          {daily_trend.map((d: any) => (
            <div key={d.date} className="flex-1 bg-green-500 rounded-t-sm" style={{ height: `${Math.max((d.calls / maxCalls) * 100, 2)}%` }} title={`${d.date}: ${d.calls}`} />
          ))}
        </div>
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border p-5">
        <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">👥 追踪用户（{install_users.length}）</h3>
        <div className="space-y-1.5">
          {install_users.map((u: any) => (
            <div key={u.user_id} className="flex justify-between p-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm">
              <span className="text-gray-700 dark:text-gray-300">{u.display_name || u.user_id}</span>
              <span className="text-xs text-gray-400">📞 {u.calls_7d}</span>
            </div>
          ))}
        </div>
      </div>

      {top_tools.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border p-5">
          <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">🔧 最常用工具</h3>
          {top_tools.map((t: any, i: number) => (
            <div key={t.tool_name} className="flex items-center gap-3 text-sm py-1">
              <span className="text-gray-400 w-5">{i + 1}.</span>
              <span className="text-gray-700 dark:text-gray-300 flex-1">{t.tool_name}</span>
              <span className="text-gray-400 text-xs">{t.count} 次</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
