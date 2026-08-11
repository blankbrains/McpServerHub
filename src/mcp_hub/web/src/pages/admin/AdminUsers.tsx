import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../../api/client'

export default function AdminUsers() {
  const [users, setUsers] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('calls')
  const [role, setRole] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({
        q,
        sort,
        page: String(page),
        page_size: '20',
      })
      if (role) params.set('role', role)
      const result = await apiGet<any[]>(`/admin/users?${params}`)
      setUsers(result.data || [])
      setTotal(result.meta?.total || 0)
    } catch {
      setUsers([])
      setTotal(0)
      setError('用户列表加载失败，请检查管理员权限后重试')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [page, sort, q, role])

  const totalPages = Math.max(1, Math.ceil(total / 20))

  return (
    <div className="max-w-6xl space-y-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">👥 用户管理</h1>
      <div className="flex gap-2 flex-wrap">
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="搜索用户名..."
          className="flex-1 min-w-[150px] px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        <select value={sort} onChange={e => setSort(e.target.value)}
          className="px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white">
          <option value="calls">按活跃度</option><option value="installs">按追踪数</option><option value="created">按注册时间</option>
        </select>
        <select value={role} onChange={e => { setRole(e.target.value); setPage(1) }}
          className="px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white">
          <option value="">全部角色</option><option value="admin">管理员</option><option value="user">普通用户</option>
        </select>
      </div>

      {error ? (
        <div className="text-center py-12 text-red-600">
          <p>{error}</p>
          <button onClick={load} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
        </div>
      ) : loading ? <div className="text-center py-8 text-gray-400">加载中...</div> : (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500">
              <th className="px-4 py-2">用户</th><th className="px-4 py-2">角色</th><th className="px-4 py-2 text-right">Server</th>
              <th className="px-4 py-2 text-right">7日调用</th><th className="px-4 py-2 text-right">7日估算 Token</th>
              <th className="px-4 py-2">最后活跃</th><th className="px-4 py-2">注册时间</th>
            </tr></thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">没有符合筛选条件的用户</td></tr>
              ) : users.map(u => (
                <tr key={u.user_id} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                  onClick={() => window.location.href = `/admin/users/${encodeURIComponent(u.user_id)}`}>
                  <td className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      {u.avatar_url ? <img src={u.avatar_url} className="w-6 h-6 rounded-full" alt="" /> : <div className="w-6 h-6 rounded-full bg-blue-500 flex items-center justify-center text-white text-xs">{u.display_name?.[0]}</div>}
                      <span className="font-medium text-gray-800 dark:text-gray-200">{u.display_name || u.user_id}</span>
                    </div>
                  </td>
                  <td className="px-4 py-2.5"><span className={`text-xs px-2 py-0.5 rounded-full ${u.role === 'admin' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>{u.role === 'admin' ? '管理员' : '用户'}</span></td>
                  <td className="px-4 py-2.5 text-right">{u.server_count}</td>
                  <td className="px-4 py-2.5 text-right">{u.calls_7d >= 1000 ? `${(u.calls_7d / 1000).toFixed(1)}K` : u.calls_7d}</td>
                  <td className="px-4 py-2.5 text-right">{u.tokens_7d >= 1000 ? `${(u.tokens_7d / 1000).toFixed(1)}K` : u.tokens_7d}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-400">{u.last_active?.slice(0, 10) || '-'}</td>
                  <td className="px-4 py-2.5 text-xs text-gray-400">{u.created_at?.slice(0, 10) || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: totalPages }, (_, i) => i + 1).filter(p => Math.abs(p - page) <= 2 || p === 1 || p === totalPages).map((p, idx, arr) => (
            <span key={p}>{idx > 0 && arr[idx - 1] !== p - 1 && <span className="px-1 text-gray-300">...</span>}
              <button onClick={() => setPage(p)} className={`w-8 h-8 rounded text-sm ${p === page ? 'bg-blue-600 text-white' : 'border hover:bg-gray-50 dark:hover:bg-gray-700 dark:text-gray-300'}`}>{p}</button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
