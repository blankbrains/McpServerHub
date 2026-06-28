import { useState, useEffect, useCallback } from 'react'
import { searchAdvanced, apiGet, ServerInfo } from '../api/client'
import ServerCard from '../components/ServerCard'

const PAGE_SIZE = 9

export default function Market() {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [tag, setTag] = useState('')
  const [author, setAuthor] = useState('')
  const [language, setLanguage] = useState('')
  const [installType, setInstallType] = useState('')
  const [securityLevel, setSecurityLevel] = useState('')
  const [sort, setSort] = useState('hot')
  const [servers, setServers] = useState<ServerInfo[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [categories, setCategories] = useState([{ id: '', name: '🏠 全部' }])
  const [tags, setTags] = useState<any[]>([])
  const [authors, setAuthors] = useState<any[]>([])
  const [showFilters, setShowFilters] = useState(false)

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const result = await searchAdvanced({
        q: query,
        category: category || undefined,
        tag: tag || undefined,
        author: author || undefined,
        language: language || undefined,
        install_type: installType || undefined,
        security_level: securityLevel || undefined,
        sort,
        page,
      })
      setServers(result.data)
      setTotal(result.meta?.total || 0)
    } catch (e) {
      console.error('Search failed:', e)
    } finally {
      setLoading(false)
    }
  }, [query, category, tag, author, language, installType, securityLevel, sort, page])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    apiGet<any[]>('/market/categories').then((r) => {
      if (r.data) setCategories([{ id: '', name: '🏠 全部' }, ...r.data.map((c: any) => ({ id: c.id, name: `${c.icon || ''} ${c.name}`, icon: c.icon }))])
    }).catch(() => {})
  }, [])

  useEffect(() => {
    apiGet<any[]>('/search/tags').then((r) => { if (r.data) setTags(r.data) }).catch(() => {})
    apiGet<any[]>('/search/authors').then((r) => { if (r.data) setAuthors(r.data) }).catch(() => {})
  }, [])

  useEffect(() => { setPage(1) }, [query, category, tag, author, language, installType, securityLevel, sort])

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">🏪 MCP 市场</h1>
        <button onClick={() => setShowFilters(!showFilters)} className="text-sm text-blue-600 hover:text-blue-800">
          {showFilters ? '收起筛选 ↑' : '展开筛选 ↓'}
        </button>
      </div>

      {/* Search + Sort */}
      <div className="flex gap-3">
        <input type="text" value={query} onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索名称、描述、标签..."
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
        <select value={sort} onChange={(e) => setSort(e.target.value)}
          className="px-3 py-2.5 border border-gray-300 rounded-lg bg-white text-sm">
          <option value="hot">🔥 热门</option>
          <option value="rating">⭐ 评分</option>
          <option value="downloads">📥 下载</option>
          <option value="new">🆕 最新</option>
          <option value="name">📄 名称</option>
        </select>
      </div>

      {/* Categories */}
      <div className="flex gap-2 flex-wrap">
        {categories.map((cat) => (
          <button key={cat.id} onClick={() => setCategory(cat.id)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${category === cat.id ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
            {cat.name}
          </button>
        ))}
      </div>

      {/* Expanded Filters */}
      {showFilters && (
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-4 space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {/* Tag */}
            <select value={tag} onChange={(e) => setTag(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm">
              <option value="">🏷️ 功能标签</option>
              {tags.map((t: any) => <option key={t.id} value={t.id}>{t.name}</option>)}
            </select>
            {/* Author */}
            <select value={author} onChange={(e) => setAuthor(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm">
              <option value="">👤 作者/组织</option>
              {authors.slice(0, 20).map((a: any) => <option key={a.id} value={a.id}>{a.name} ({a.count})</option>)}
            </select>
            {/* Language */}
            <select value={language} onChange={(e) => setLanguage(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm">
              <option value="">💻 编程语言</option>
              <option value="python">🐍 Python</option>
              <option value="typescript">📘 TypeScript</option>
              <option value="go">🔵 Go</option>
              <option value="rust">🦀 Rust</option>
              <option value="java">☕ Java</option>
              <option value="c#">#️⃣ C#</option>
            </select>
            {/* Install type */}
            <select value={installType} onChange={(e) => setInstallType(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-lg bg-white text-sm">
              <option value="">📦 安装方式</option>
              <option value="npx">📦 npx</option>
              <option value="pip">🐍 pip</option>
              <option value="go">🔵 go install</option>
            </select>
          </div>
          <div className="flex items-center gap-2 text-xs text-gray-400">
            <span className="font-medium">🏷️ 功能标签:</span>
            <button onClick={() => setTag('')}
              className={`px-2 py-0.5 rounded ${tag === '' ? 'bg-blue-100 text-blue-600' : 'hover:bg-gray-200'}`}>全部</button>
            {tags.slice(0, 15).map((t: any) => (
              <button key={t.id} onClick={() => setTag(t.id)}
                className={`px-2 py-0.5 rounded ${tag === t.id ? 'bg-blue-100 text-blue-600' : 'hover:bg-gray-200'}`}>
                {t.name}
              </button>
            ))}
            {tags.length > 15 && <span className="text-gray-300">···</span>}
          </div>
        </div>
      )}

      <p className="text-sm text-gray-500">
        共 {total} 个结果 {totalPages > 1 && <span>· 第 {page}/{totalPages} 页</span>}
      </p>

      {loading ? (
        <div className="flex items-center justify-center h-64"><div className="text-gray-400">搜索中...</div></div>
      ) : (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {servers.map((s) => (<ServerCard key={s.id} server={s} />))}
            {servers.length === 0 && <div className="col-span-3 text-center py-16 text-gray-400">😕 没有找到匹配的 Server</div>}
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-center gap-2 py-6">
              <button onClick={() => setPage(Math.max(1, page - 1))} disabled={page <= 1}
                className="px-3 py-1.5 rounded-lg border border-gray-300 text-sm disabled:opacity-40 hover:bg-gray-50">← 上一页</button>
              {Array.from({ length: totalPages }, (_, i) => i + 1)
                .filter((p) => p === 1 || p === totalPages || Math.abs(p - page) <= 1)
                .map((p, idx, arr) => (
                  <span key={p} className="flex items-center gap-1">
                    {idx > 0 && arr[idx - 1] !== p - 1 && <span className="px-1 text-gray-400">...</span>}
                    <button onClick={() => setPage(p)}
                      className={`w-9 h-9 rounded-lg text-sm font-medium ${page === p ? 'bg-blue-600 text-white' : 'border border-gray-300 hover:bg-gray-50'}`}>{p}</button>
                  </span>
                ))}
              <button onClick={() => setPage(Math.min(totalPages, page + 1))} disabled={page >= totalPages}
                className="px-3 py-1.5 rounded-lg border border-gray-300 text-sm disabled:opacity-40 hover:bg-gray-50">下一页 →</button>
            </div>
          )}
        </>
      )}
    </div>
  )
}
