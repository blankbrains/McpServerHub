import { useState, useEffect } from 'react'
import { apiDelete, apiGet } from '../../api/client'

export default function AdminReviews() {
  const [reviews, setReviews] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [msg, setMsg] = useState('')
  const [error, setError] = useState('')
  const load = async () => {
    setLoading(true)
    setError('')
    try {
      const result = await apiGet<any[]>(`/admin/reviews?page=${page}`)
      setReviews(result.data || [])
      setTotal(result.meta?.total || 0)
    } catch {
      setReviews([])
      setTotal(0)
      setError('评价列表加载失败，请检查管理员权限后重试')
    } finally {
      setLoading(false)
    }
  }
  useEffect(() => { load() }, [page])

  const deleteReview = async (id: number) => {
    if (!window.confirm('确定删除此评价？')) return
    try {
      const r: any = await apiDelete(`/admin/reviews/${id}`)
      setMsg(r.success ? '✅ 已删除' : `❌ ${r.error}`)
      if (r.success) load()
    } catch { setMsg('❌ 删除失败') }
    setTimeout(() => setMsg(''), 2000)
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="max-w-5xl space-y-4">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">🛡️ 评价审核</h1>
      {msg && <div className={`p-2 rounded-lg text-sm ${msg.startsWith('✅') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>{msg}</div>}
      {error ? (
        <div className="text-center py-12 text-red-600">
          <p>{error}</p>
          <button onClick={load} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
        </div>
      ) : (
      <>
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="border-b border-gray-200 dark:border-gray-700 text-left text-xs text-gray-500">
            <th className="px-4 py-2 w-12">ID</th><th className="px-4 py-2">Server</th><th className="px-4 py-2">用户</th>
            <th className="px-4 py-2 w-12">评分</th><th className="px-4 py-2">内容</th><th className="px-4 py-2">时间</th><th className="px-4 py-2 w-16">操作</th>
            </tr></thead>
            <tbody>
              {reviews.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-10 text-center text-gray-400">暂无评价</td></tr>
              ) : reviews.map(r => (
              <tr key={r.id} className="border-b border-gray-100 dark:border-gray-700">
                <td className="px-4 py-2 text-xs text-gray-400">{r.id}</td>
                <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-300">{r.server_name}</td>
                <td className="px-4 py-2 text-xs">{r.user_id}</td>
                <td className="px-4 py-2 text-xs">{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</td>
                <td className="px-4 py-2 text-xs text-gray-500 max-w-xs truncate">{r.content}</td>
                <td className="px-4 py-2 text-xs text-gray-400">{r.created_at?.slice(0, 10)}</td>
                <td className="px-4 py-2"><button onClick={() => deleteReview(r.id)} className="text-xs text-red-500 hover:text-red-700">删除</button></td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
        <div className="text-xs text-gray-400">共 {total} 条 · 第 {page}/{Math.max(1, Math.ceil(total / 20))} 页</div>
      </>
      )}
    </div>
  )
}
