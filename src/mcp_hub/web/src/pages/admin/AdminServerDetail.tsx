import { useState, useEffect } from 'react'
import { Link, useParams } from 'react-router-dom'
import { apiGet, apiPost } from '../../api/client'

interface Notice {
  type: 'success' | 'error'
  text: string
}

export default function AdminServerDetail() {
  const { serverId } = useParams<{ serverId: string }>()
  const [data, setData] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState<Notice | null>(null)
  const [saving, setSaving] = useState(false)
  const [securitySelection, setSecuritySelection] = useState('')

  const load = async (showLoading = true) => {
    if (!serverId) return
    if (showLoading) setLoading(true)
    setError('')
    try {
      const result = await apiGet<any>(`/admin/servers/${encodeURIComponent(serverId)}`)
      setData(result.data || null)
    } catch {
      setData(null)
      setError('Server 详情加载失败，请检查管理员权限后重试')
    } finally {
      if (showLoading) setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [serverId])

  const updateServer = async (path: string, body: any): Promise<boolean> => {
    setSaving(true)
    setNotice(null)
    try {
      const result: any = await apiPost(path, body)
      if (!result.success) throw new Error(result.error || result.message || '操作失败')
      setNotice({ type: 'success', text: result.message || '操作成功' })
      await load(false)
      return true
    } catch (requestError) {
      setNotice({
        type: 'error',
        text: requestError instanceof Error ? requestError.message : '操作失败',
      })
      return false
    } finally {
      setSaving(false)
    }
  }

  if (loading) return <div role="status" className="text-center py-16 text-gray-400">加载中...</div>
  if (error || !data) return (
    <div role="alert" className="text-center py-16 text-red-600">
      <p>{error || 'Server 不存在'}</p>
      <button type="button" onClick={() => void load()} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
    </div>
  )

  const { server, stats, install_users = [], daily_trend = [], top_tools = [] } = data
  const maxCalls = Math.max(...daily_trend.map((d: any) => d.calls), 1)
  const restoring = !server.market_visible

  return (
    <div className="max-w-4xl space-y-5">
      <header>
        <Link to="/admin/servers" className="text-sm text-blue-600 hover:underline dark:text-blue-400">← 返回 Server 与市场</Link>
        <h1 className="mt-2 break-words text-2xl font-bold text-gray-900 dark:text-white">📦 {server.name || server.server_id}</h1>
      </header>
      {notice && (
        <p
          role={notice.type === 'success' ? 'status' : 'alert'}
          className={`p-3 text-sm rounded-lg ${notice.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}
        >
          {notice.text}
        </p>
      )}

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 p-5 dark:border-gray-700">
        <p className="break-words text-sm text-gray-500 dark:text-gray-400">{server.description}</p>
        <div className="flex flex-wrap gap-2 mt-2 items-center">
          <span className={`text-xs px-2 py-0.5 rounded-full ${server.security_level === 'blocked' ? 'bg-red-100 text-red-700' : server.security_level === 'verified' ? 'bg-green-100 text-green-700' : server.security_level === 'reviewed' ? 'bg-yellow-100 text-yellow-700' : 'bg-gray-100 text-gray-600'}`}>安全: {server.security_level}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${server.market_visible ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
            市场：{server.market_visible ? '可见' : '已隐藏'}
          </span>
          {/* 管理操作 */}
          <button type="button" onClick={async () => {
            if (!window.confirm(restoring ? '确定恢复此 Server 的市场可见性？' : '确定下架此 Server？')) return
            const action = restoring ? 'unblock' : 'block'
            await updateServer(`/admin/servers/${encodeURIComponent(server.server_id)}/toggle`, { action })
          }} disabled={saving} className={`text-xs px-2 py-1 rounded disabled:opacity-50 ${restoring ? 'bg-green-50 text-green-700 hover:bg-green-100' : 'bg-red-50 text-red-600 hover:bg-red-100'}`}>
            {saving ? '处理中...' : restoring ? '恢复上架' : '下架'}
          </button>
          <select aria-label="调整 Server 安全等级" value={securitySelection} onChange={async (e) => {
            const level = e.target.value
            setSecuritySelection(level)
            if (!level) return
            if (!window.confirm(`确定将安全等级设为 ${level}？`)) {
              setSecuritySelection('')
              return
            }
            await updateServer(`/admin/servers/${encodeURIComponent(server.server_id)}/security`, { level })
            setSecuritySelection('')
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

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[['追踪用户', stats.install_count], ['7日调用', stats.calls_7d], ['7日估算 Token', stats.tokens_7d >= 1000 ? `${(stats.tokens_7d/1000).toFixed(1)}K` : stats.tokens_7d], ['评分', `${server.rating?.toFixed(1) || '-'}⭐`]].map(([l, v]) => (
          <div key={l as string} className="bg-white dark:bg-gray-800 rounded-xl border p-3 text-center">
            <p className="text-xl font-bold text-gray-900 dark:text-white">{v}</p><p className="text-xs text-gray-500">{l}</p>
          </div>
        ))}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 p-5 dark:border-gray-700">
        <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">📈 每日调用趋势</h3>
        {daily_trend.length > 0 ? <div className="flex items-end gap-1 h-32">
          {daily_trend.map((d: any) => (
            <div key={d.date} className="flex-1 bg-green-500 rounded-t-sm" style={{ height: `${Math.max((d.calls / maxCalls) * 100, 2)}%` }} title={`${d.date}: ${d.calls}`} />
          ))}
        </div> : <p className="py-8 text-sm text-gray-400">最近 30 天暂无工具调用。</p>}
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 p-5 dark:border-gray-700">
        <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">👥 追踪用户（共 {stats.install_count || 0}）</h3>
        {install_users.length < (stats.install_count || 0) && <p className="mb-3 text-xs text-gray-400">按最近 7 日调用量显示前 {install_users.length} 位。</p>}
        <div className="space-y-1.5">
          {install_users.length === 0 ? <p className="py-6 text-sm text-gray-400">当前没有用户追踪此 Server。</p> : install_users.map((u: any) => (
            <div key={u.user_id} className="flex min-w-0 justify-between gap-3 p-2 bg-gray-50 dark:bg-gray-700 rounded-lg text-sm">
              <span className="min-w-0 flex-1 break-all text-gray-700 dark:text-gray-300">{u.display_name || u.user_id}</span>
              <span className="shrink-0 text-xs text-gray-400">📞 {u.calls_7d}</span>
            </div>
          ))}
        </div>
      </div>

      {top_tools.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 p-5 dark:border-gray-700">
          <h3 className="font-semibold mb-3 text-gray-900 dark:text-white">🔧 最常用工具</h3>
          {top_tools.map((t: any, i: number) => (
            <div key={t.tool_name} className="flex min-w-0 items-center gap-3 text-sm py-1">
              <span className="w-5 shrink-0 text-gray-400">{i + 1}.</span>
              <span className="min-w-0 flex-1 break-all text-gray-700 dark:text-gray-300">{t.tool_name}</span>
              <span className="shrink-0 text-gray-400 text-xs">{t.count} 次</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
