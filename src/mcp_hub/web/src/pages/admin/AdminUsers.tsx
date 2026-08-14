import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiDownload, apiGet } from '../../api/client'

function fmtNum(value: number | undefined): string {
  const n = Number(value || 0)
  return n >= 1_000 ? `${(n / 1_000).toFixed(1)}K` : String(n)
}

export default function AdminUsers() {
  const navigate = useNavigate()
  const [users, setUsers] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [query, setQuery] = useState('')
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('calls')
  const [role, setRole] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [exporting, setExporting] = useState(false)
  const requestVersion = useRef(0)

  const load = async () => {
    const version = ++requestVersion.current
    setLoading(true)
    setError('')
    try {
      const params = new URLSearchParams({ q, sort, page: String(page), page_size: '20' })
      if (role) params.set('role', role)
      const result = await apiGet<any[]>(`/admin/users?${params}`)
      if (version !== requestVersion.current) return
      setUsers(result.data || [])
      setTotal(result.meta?.total || 0)
    } catch {
      if (version !== requestVersion.current) return
      setUsers([])
      setTotal(0)
      setError('用户与设备列表加载失败，请检查管理员权限后重试')
    } finally {
      if (version === requestVersion.current) setLoading(false)
    }
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQ(query)
      setPage(1)
    }, 300)
    return () => window.clearTimeout(timer)
  }, [query])

  useEffect(() => {
    void load()
    return () => { requestVersion.current += 1 }
  }, [page, sort, q, role])

  const totalPages = Math.max(1, Math.ceil(total / 20))

  return (
    <div className="max-w-6xl space-y-5">
      <header>
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">OPERATIONS / USERS</p>
            <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">👥 用户与设备</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">查看账号活跃度、Gateway 接入和设备在线状态。</p>
          </div>
          <button
            type="button"
            disabled={exporting}
            onClick={async () => {
              setExporting(true)
              setError('')
              try {
                await apiDownload('/admin/export/users', 'mcp-hub-users.csv')
              } catch {
                setError('用户数据导出失败，请稍后重试')
              } finally {
                setExporting(false)
              }
            }}
            className="border border-gray-300 px-3 py-2 text-sm text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-600 dark:text-gray-200 dark:hover:bg-gray-800"
          >
            {exporting ? '正在导出...' : '导出全部 CSV'}
          </button>
        </div>
      </header>

      <section className="flex flex-wrap gap-2">
        <input type="search" aria-label="搜索用户" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索用户名..."
          className="min-w-[220px] flex-1 border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white" />
        <select aria-label="用户排序方式" value={sort} onChange={event => { setSort(event.target.value); setPage(1) }}
          className="border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white">
          <option value="calls">按调用活跃度</option>
          <option value="installs">按追踪 Server</option>
          <option value="created">按注册时间</option>
        </select>
        <select aria-label="用户角色筛选" value={role} onChange={event => { setRole(event.target.value); setPage(1) }}
          className="border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800 dark:text-white">
          <option value="">全部角色</option>
          <option value="admin">管理员</option>
          <option value="user">普通用户</option>
        </select>
      </section>

      {error ? (
        <div role="alert" className="py-12 text-center text-red-600">
          <p>{error}</p>
          <button type="button" onClick={() => void load()} className="mt-3 text-sm text-blue-600 hover:underline">重试</button>
        </div>
      ) : loading ? (
        <div role="status" className="py-12 text-center text-sm text-gray-400">正在加载用户与设备...</div>
      ) : (
        <div className="overflow-x-auto border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-left text-xs text-gray-500 dark:border-gray-700">
                <th className="px-4 py-3">用户</th>
                <th className="px-4 py-3">角色</th>
                <th className="px-4 py-3 text-right">Server</th>
                <th className="px-4 py-3 text-right">设备 / 在线</th>
                <th className="px-4 py-3 text-right">7 日调用</th>
                <th className="px-4 py-3 text-right">7 日估算 Token</th>
                <th className="px-4 py-3">最后活跃</th>
                <th className="px-4 py-3">注册时间</th>
              </tr>
            </thead>
            <tbody>
              {users.length === 0 ? (
                <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-400">没有符合筛选条件的用户</td></tr>
              ) : users.map(user => (
                <tr
                  key={user.user_id}
                  tabIndex={0}
                  role="link"
                  aria-label={`查看用户 ${user.display_name || user.user_id}`}
                  className="cursor-pointer border-b border-gray-100 hover:bg-blue-50/40 focus:bg-blue-50/40 focus:outline-none dark:border-gray-700 dark:hover:bg-gray-700 dark:focus:bg-gray-700"
                  onClick={() => navigate(`/admin/users/${encodeURIComponent(user.user_id)}`)}
                  onKeyDown={event => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault()
                      navigate(`/admin/users/${encodeURIComponent(user.user_id)}`)
                    }
                  }}
                >
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2">
                      {user.avatar_url
                        ? <img src={user.avatar_url} className="h-7 w-7 rounded-full" alt="" />
                        : <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs text-white">{user.display_name?.[0] || '?'}</div>}
                      <div className="min-w-0">
                        <p className="truncate font-medium text-gray-800 dark:text-gray-200">{user.display_name || user.user_id}</p>
                        <p className="truncate text-[11px] text-gray-400">@{user.user_id}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`text-xs ${user.role === 'admin' ? 'text-purple-700 dark:text-purple-300' : 'text-gray-500'}`}>
                      {user.role === 'admin' ? '🛡️ 管理员' : '普通用户'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{user.server_count || 0}</td>
                  <td className="px-4 py-3 text-right">
                    <span className={user.online_device_count > 0 ? 'font-medium text-green-600' : 'text-gray-400'}>
                      {user.device_count || 0} / {user.online_device_count || 0}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{fmtNum(user.calls_7d)}</td>
                  <td className="px-4 py-3 text-right text-gray-600 dark:text-gray-300">{fmtNum(user.tokens_7d)}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{user.last_active?.slice(0, 16) || '-'}</td>
                  <td className="px-4 py-3 text-xs text-gray-400">{user.created_at?.slice(0, 10) || '-'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="flex justify-center gap-2">
          {Array.from({ length: totalPages }, (_, index) => index + 1)
            .filter(value => Math.abs(value - page) <= 2 || value === 1 || value === totalPages)
            .map((value, index, visible) => (
              <span key={value}>
                {index > 0 && visible[index - 1] !== value - 1 && <span className="px-1 text-gray-300">...</span>}
                <button type="button" aria-current={value === page ? 'page' : undefined} aria-label={`第 ${value} 页`} onClick={() => setPage(value)} className={`h-8 w-8 text-sm ${value === page ? 'bg-blue-600 text-white' : 'border border-gray-300 text-gray-600 hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700'}`}>
                  {value}
                </button>
              </span>
            ))}
        </div>
      )}
    </div>
  )
}
