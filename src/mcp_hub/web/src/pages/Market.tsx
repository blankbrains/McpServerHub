import { useState, useEffect } from 'react'
import { searchServers, ServerInfo } from '../api/client'
import ServerCard from '../components/ServerCard'

const CATEGORIES = [
  { id: '', name: '全部' },
  { id: 'browser', name: '浏览器' },
  { id: 'database', name: '数据库' },
  { id: 'developer-tools', name: '开发工具' },
  { id: 'ai', name: 'AI' },
  { id: 'communication', name: '通信' },
  { id: 'monitoring', name: '监控' },
  { id: 'cloud', name: '云服务' },
]

export default function Market() {
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [sort, setSort] = useState('hot')
  const [servers, setServers] = useState<ServerInfo[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const result = await searchServers({ q: query, category: category || undefined, sort, page: 1 })
        setServers(result.data)
        setTotal(result.meta.total)
      } catch (e) {
        console.error('Search failed:', e)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [query, category, sort])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">🏪 MCP 市场</h1>
      <p className="text-gray-500">发现可用的 MCP Server，一键安装，立即使用</p>

      {/* Search bar */}
      <div className="flex gap-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="搜索 MCP Server..."
          className="flex-1 px-4 py-2.5 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value)}
          className="px-3 py-2.5 border border-gray-300 rounded-lg bg-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="hot">🔥 热门</option>
          <option value="rating">⭐ 评分</option>
          <option value="downloads">📥 下载</option>
          <option value="new">🆕 最新</option>
        </select>
      </div>

      {/* Categories */}
      <div className="flex gap-2 flex-wrap">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.id}
            onClick={() => setCategory(cat.id)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-colors ${
              category === cat.id
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {cat.name}
          </button>
        ))}
      </div>

      {/* Results */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">共 {total} 个结果</p>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-gray-400">搜索中...</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {servers.map((s) => (
            <ServerCard key={s.id} server={s} />
          ))}
          {servers.length === 0 && (
            <div className="col-span-3 text-center py-16 text-gray-400">
              😕 没有找到匹配的 Server
            </div>
          )}
        </div>
      )}
    </div>
  )
}
