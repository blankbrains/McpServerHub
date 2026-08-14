import { useEffect, useRef, useState } from 'react'
import { apiDelete, apiGet } from '../../api/client'

interface Notice {
  type: 'success' | 'error'
  text: string
}

const PAGE_SIZE = 20

export default function AdminReviews() {
  const [reviews, setReviews] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [notice, setNotice] = useState<Notice | null>(null)
  const [error, setError] = useState('')
  const [expandedReviewId, setExpandedReviewId] = useState<number | null>(null)
  const [deletingId, setDeletingId] = useState<number | null>(null)
  const requestVersion = useRef(0)
  const deletingReview = useRef(false)

  const load = async (showLoading = true) => {
    const version = ++requestVersion.current
    if (showLoading) setLoading(true)
    setError('')
    try {
      const result = await apiGet<any[]>(`/admin/reviews?page=${page}`)
      if (version !== requestVersion.current) return
      setReviews(result.data || [])
      setTotal(result.meta?.total || 0)
    } catch {
      if (version !== requestVersion.current) return
      setReviews([])
      setTotal(0)
      setError('评价列表加载失败，请检查管理员权限后重试')
    } finally {
      if (showLoading && version === requestVersion.current) setLoading(false)
    }
  }
  useEffect(() => {
    void load()
    return () => { requestVersion.current += 1 }
  }, [page])

  const deleteReview = async (review: any) => {
    if (deletingReview.current) return
    if (!window.confirm(`确定删除 ${review.user_id} 对 ${review.server_name || review.server_id} 的评价？`)) return
    deletingReview.current = true
    setDeletingId(review.id)
    setNotice(null)
    try {
      const result: any = await apiDelete(`/admin/reviews/${review.id}`)
      if (!result.success) throw new Error(result.error || result.message || '删除失败')
      setNotice({ type: 'success', text: result.message || '评价已删除' })
      setExpandedReviewId(current => current === review.id ? null : current)
      const nextTotal = Math.max(0, total - 1)
      const nextPage = Math.min(page, Math.max(1, Math.ceil(nextTotal / PAGE_SIZE)))
      if (nextPage !== page) setPage(nextPage)
      else await load(false)
    } catch (requestError) {
      setNotice({
        type: 'error',
        text: requestError instanceof Error ? requestError.message : '删除失败',
      })
    } finally {
      deletingReview.current = false
      setDeletingId(null)
    }
  }

  if (loading) return <div role="status" className="text-center py-16 text-gray-400">加载中...</div>
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  return (
    <div className="max-w-5xl space-y-4">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-blue-600 dark:text-blue-400">OPERATIONS / MODERATION</p>
        <h1 className="mt-1 text-2xl font-bold text-gray-900 dark:text-white">🛡️ 内容审核</h1>
        <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">审核用户评价；Server 下架、安全等级和市场可见性在 Server 详情中处理。</p>
      </header>
      {notice && (
        <div role={notice.type === 'success' ? 'status' : 'alert'} className={`p-2 rounded-lg text-sm ${notice.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {notice.text}
        </div>
      )}
      {error ? (
        <div role="alert" className="text-center py-12 text-red-600">
          <p>{error}</p>
          <button type="button" onClick={() => void load()} className="mt-3 text-sm text-blue-600 hover:text-blue-800 underline">重试</button>
        </div>
      ) : (
      <>
        <div className="space-y-3 md:hidden">
          {reviews.length === 0 ? (
            <div className="border border-gray-200 bg-white px-4 py-10 text-center text-sm text-gray-400 dark:border-gray-700 dark:bg-gray-800">暂无评价</div>
          ) : reviews.map(r => (
            <article key={r.id} className="rounded-lg border border-gray-200 bg-white p-4 dark:border-gray-700 dark:bg-gray-800">
              <div className="flex min-w-0 items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="break-words text-sm font-medium text-gray-800 dark:text-gray-200">{r.server_name}</p>
                  <p className="mt-1 break-all text-xs text-gray-400">{r.user_id}</p>
                </div>
                <span className="shrink-0 text-xs" aria-label={`${r.rating} 星`}>{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</span>
              </div>
              <div className="mt-3">
                <ReviewContent
                  review={r}
                  expanded={expandedReviewId === r.id}
                  idPrefix="mobile"
                  onToggle={() => setExpandedReviewId(current => current === r.id ? null : r.id)}
                />
              </div>
              <div className="mt-4 flex items-center justify-between gap-3">
                <span className="text-xs text-gray-400">{r.created_at?.slice(0, 10)} · #{r.id}</span>
                <DeleteReviewButton
                  review={r}
                  deletingId={deletingId}
                  onDelete={() => void deleteReview(r)}
                />
              </div>
            </article>
          ))}
        </div>

        <div className="hidden overflow-x-auto rounded-xl border border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800 md:block">
        <table className="min-w-[900px] text-sm">
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
                <td className="px-4 py-2 text-xs text-gray-600 dark:text-gray-300"><span className="block max-w-48 break-words">{r.server_name}</span></td>
                <td className="px-4 py-2 text-xs"><span className="block max-w-48 break-all">{r.user_id}</span></td>
                <td className="px-4 py-2 text-xs">{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</td>
                <td className="px-4 py-2 text-xs text-gray-500 dark:text-gray-400">
                  <ReviewContent
                    review={r}
                    expanded={expandedReviewId === r.id}
                    idPrefix="desktop"
                    onToggle={() => setExpandedReviewId(current => current === r.id ? null : r.id)}
                  />
                </td>
                <td className="px-4 py-2 text-xs text-gray-400">{r.created_at?.slice(0, 10)}</td>
                <td className="px-4 py-2">
                  <DeleteReviewButton
                    review={r}
                    deletingId={deletingId}
                    onDelete={() => void deleteReview(r)}
                  />
                </td>
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
      )}
    </div>
  )
}

function ReviewContent({
  review,
  expanded,
  idPrefix,
  onToggle,
}: {
  review: any
  expanded: boolean
  idPrefix: string
  onToggle: () => void
}) {
  const contentId = `${idPrefix}-review-content-${review.id}`
  return (
    <div className="min-w-0 max-w-md text-xs text-gray-500 dark:text-gray-400">
      <p id={contentId} className={expanded ? 'whitespace-pre-wrap break-words leading-5' : 'truncate'}>
        {review.content || '（无文字评价）'}
      </p>
      {(review.content?.length || 0) > 80 && (
        <button
          type="button"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={onToggle}
          className="mt-1 text-xs text-blue-600 hover:underline dark:text-blue-400"
        >
          {expanded ? '收起全文' : '展开全文'}
        </button>
      )}
    </div>
  )
}

function DeleteReviewButton({
  review,
  deletingId,
  onDelete,
}: {
  review: any
  deletingId: number | null
  onDelete: () => void
}) {
  return (
    <button
      type="button"
      aria-label={`删除评价 #${review.id}`}
      disabled={deletingId !== null}
      onClick={onDelete}
      className="text-xs text-red-500 hover:text-red-700 disabled:opacity-50"
    >
      {deletingId === review.id ? '删除中...' : '删除'}
    </button>
  )
}
