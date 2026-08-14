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
    let cancelled = false
    setLoading(true)
    setError('')
    const qs = new URLSearchParams({ page: String(page), page_size: '50' })
    if (actionFilter) qs.set('action_type', actionFilter)
    apiGet<any[]>(`/admin/audit?${qs}`)
      .then(result => {
        if (cancelled) return
        setLogs(result.data || [])
        setTotal(result.meta?.total || 0)
      })
      .catch(() => {
        if (cancelled) return
        setLogs([])
        setTotal(0)
        setError('审计日志加载失败，请检查管理员权限后重试')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [page, actionFilter, reloadKey])

  const totalPages = Math.max(1, Math.ceil(total / 50))

  if (loading) return <div role="status" className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="max-w-5xl space-y-4">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">OPERATIONS / AUDIT</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">📋 操作审计</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">记录管理员的角色修改、评价删除、Server 下架和安全等级调整。</p>
      </header>
      <div className="flex gap-2">
        <select aria-label="审计操作筛选" value={actionFilter} onChange={e => { setActionFilter(e.target.value); setPage(1) }}
          className="px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white">
          <option value="">全部操作</option>
          <option value="修改用户角色">修改角色</option>
          <option value="删除评价">删除评价</option>
          <option value="下架 Server">下架 Server</option>
          <option value="恢复 Server">恢复 Server</option>
          <option value="调整安全等级">调整安全等级</option>
        </select>
      </div>

      {error ? (
        <div role="alert" className="text-center py-12 text-red-600">
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
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>共 {total} 条 · 第 {page}/{totalPages} 页</span>
          {totalPages > 1 && (
            <div className="flex gap-2">
              <button type="button" disabled={page <= 1} onClick={() => setPage(value => value - 1)}
                aria-label="上一页"
                className="border border-gray-300 px-2 py-1 text-gray-600 disabled:opacity-40 dark:border-gray-600 dark:text-gray-300">
                上一页
              </button>
              <button type="button" disabled={page >= totalPages} onClick={() => setPage(value => value + 1)}
                aria-label="下一页"
                className="border border-gray-300 px-2 py-1 text-gray-600 disabled:opacity-40 dark:border-gray-600 dark:text-gray-300">
                下一页
              </button>
            </div>
          )}
        </div>
      </>
      }
    </div>
  )
}
