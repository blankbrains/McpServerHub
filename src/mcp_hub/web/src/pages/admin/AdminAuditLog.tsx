import { useState, useEffect } from 'react'
import { apiGet } from '../../api/client'

export default function AdminAuditLog() {
  const [logs, setLogs] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [actionFilter, setActionFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)
  useEffect(() => {
    setLoading(true)
    setError('')
    const qs = new URLSearchParams({ page: String(page), page_size: '50' })
    if (actionFilter) qs.set('action_type', actionFilter)
    apiGet<any[]>(`/admin/audit?${qs}`)
      .then(result => {
        setLogs(result.data || [])
        setTotal(result.meta?.total || 0)
      })
      .catch(() => {
        setLogs([])
        setTotal(0)
        setError('审计日志加载失败，请检查管理员权限后重试')
      })
      .finally(() => setLoading(false))
  }, [page, actionFilter, reloadKey])

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">📋 操作审计</h1>
      <div className="flex gap-2">
        <select value={actionFilter} onChange={e => { setActionFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white">
          <option value="">全部操作</option><option value="角色">修改角色</option><option value="删除">删除操作</option>
        </select>
      </div>

      {error ? (
        <div className="text-center py-12 text-red-600">
          <p>{error}</p>
          <button onClick={() => setReloadKey(value => value + 1)} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
        </div>
      ) : <>
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500">
            <th className="px-4 py-2 w-32">时间</th><th className="px-4 py-2">操作人</th><th className="px-4 py-2">操作</th><th className="px-4 py-2">详情</th>
          </tr></thead>
          <tbody>
            {logs.length === 0 ? (
              <tr><td colSpan={4} className="text-center py-8 text-gray-400">暂无审计记录</td></tr>
            ) : logs.map(l => (
              <tr key={l.id} className="border-b border-gray-100 dark:border-gray-700">
                <td className="px-4 py-2 text-xs text-gray-400">{l.created_at?.slice(0, 16)}</td>
                <td className="px-4 py-2 text-xs">{l.user_id}</td>
                <td className="px-4 py-2 text-xs font-medium text-gray-700 dark:text-gray-300">{l.action}</td>
                <td className="px-4 py-2 text-xs text-gray-400">{l.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <div className="text-xs text-gray-400">共 {total} 条</div>
      </>
      }
    </div>
  )
}
