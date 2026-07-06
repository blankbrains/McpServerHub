import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { getAuthState } from '../../api/client'

export default function AdminServers() {
  const [servers, setServers] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [q, setQ] = useState('')
  const [sort, setSort] = useState('installs')
  const [loading, setLoading] = useState(true)
  const uid = getAuthState().userId || 'anonymous'

  const load = () => {
    setLoading(true)
    fetch(`/api/v1/admin/servers?q=${encodeURIComponent(q)}&sort=${sort}&page=${page}&page_size=20`, { headers: { 'x-user-id': uid } })
      .then(r => r.json()).then(r => { setServers(r.data || []); setTotal(r.meta?.total || 0) })
      .catch(() => {}).finally(() => setLoading(false))
  }
  useEffect(() => { load() }, [page, sort])
  useEffect(() => { setPage(1); load() }, [q])

  const totalPages = Math.max(1, Math.ceil(total / 20))
  const secLabels: Record<string, string> = { verified: '🟢', reviewed: '🟡', unreviewed: '🟠', blocked: '🔴' }

  return (
    <div className="max-w-6xl space-y-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">📦 Server 管理</h1>
      <div className="flex gap-2 flex-wrap">
        <input value={q} onChange={e => setQ(e.target.value)} placeholder="搜索 Server..."
          className="flex-1 min-w-[150px] px-3 py-2 border rounded-lg text-sm dark:bg-gray-700 dark:border-gray-600 dark:text-white" />
        <select value={sort} onChange={e => setSort(e.target.value)}
          className="px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white">
          <option value="installs">按安装数</option><option value="calls">按调用量</option><option value="rating">按评分</option>
        </select>
        <select onChange={e => { setQ(e.target.value); setPage(1) }}
          className="px-3 py-2 border rounded-lg text-sm bg-white dark:bg-gray-700 dark:border-gray-600 dark:text-white">
          <option value="">全部安全等级</option>
          <option value="verified">🟢 安全认证</option><option value="reviewed">🟡 已审查</option>
          <option value="unreviewed">🟠 未审查</option><option value="blocked">🔴 已阻止</option>
        </select>
      </div>

      {loading ? <div className="text-center py-8 text-gray-400">加载中...</div> : (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500">
              <th className="px-4 py-2">Server</th><th className="px-4 py-2">分类</th><th className="px-4 py-2 text-right">安装</th>
              <th className="px-4 py-2 text-right">7日调用</th><th className="px-4 py-2 text-right">7日Token</th>
              <th className="px-4 py-2 text-right">评分</th><th className="px-4 py-2">安全</th>
            </tr></thead>
            <tbody>
              {servers.map(s => (
                <tr key={s.server_id} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700 cursor-pointer"
                  onClick={() => window.location.href = `/admin/servers/${encodeURIComponent(s.server_id)}`}>
                  <td className="px-4 py-2.5 font-medium text-gray-800 dark:text-gray-200">{s.name || s.server_id}</td>
                  <td className="px-4 py-2.5"><div className="flex gap-1">{s.categories?.slice(0, 2).map((c: string) => <span key={c} className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-700 rounded">{c}</span>)}</div></td>
                  <td className="px-4 py-2.5 text-right">{s.install_count}</td>
                  <td className="px-4 py-2.5 text-right">{s.calls_7d >= 1000 ? `${(s.calls_7d/1000).toFixed(1)}K` : s.calls_7d}</td>
                  <td className="px-4 py-2.5 text-right">{s.tokens_7d >= 1000 ? `${(s.tokens_7d/1000).toFixed(1)}K` : s.tokens_7d}</td>
                  <td className="px-4 py-2.5 text-right">{s.rating?.toFixed(1) || '-'}</td>
                  <td className="px-4 py-2.5">{secLabels[s.security_level] || s.security_level}</td>
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
              <button onClick={() => setPage(p)} className={`w-8 h-8 rounded text-sm ${p === page ? 'bg-blue-600 text-white' : 'border hover:bg-gray-50 dark:text-gray-300 dark:hover:bg-gray-700'}`}>{p}</button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
