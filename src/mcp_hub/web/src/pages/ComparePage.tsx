import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { searchServers, ServerInfo, getServerReliability } from '../api/client'

const COMPARE_DIMENSIONS = [
  { key: 'rating', label: '评分', format: (v: any) => `${v} ⭐` },
  { key: 'download_count', label: '下载量', format: (v: any) => v >= 1000 ? `${(v/1000).toFixed(1)}K` : String(v) },
  { key: 'review_count', label: '评价数', format: (v: any) => String(v) },
  { key: 'security_level', label: '安全等级', format: (v: any) => v },
  { key: 'license', label: '许可证', format: (v: any) => v || '-' },
  { key: 'version', label: '版本', format: (v: any) => v || '?' },
]

export default function ComparePage() {
  const [query, setQuery] = useState('')
  const [searchResults, setSearchResults] = useState<ServerInfo[]>([])
  const [selected, setSelected] = useState<ServerInfo[]>([])
  const [searching, setSearching] = useState(false)
  const [reliabilities, setReliabilities] = useState<Record<string, any>>({})

  const maxSlots = 4

  const handleSearch = async () => {
    if (!query.trim()) return
    setSearching(true)
    try {
      const r = await searchServers({ q: query, page: 1 })
      setSearchResults(r.data.filter(s => !selected.find(sel => sel.id === s.id)))
    } catch {} finally { setSearching(false) }
  }

  const addServer = async (s: ServerInfo) => {
    if (selected.length >= maxSlots) return
    if (selected.find(x => x.id === s.id)) return
    setSelected(prev => [...prev, s])
    setSearchResults(prev => prev.filter(x => x.id !== s.id))
    setQuery('')
    // 加载可靠性数据
    try {
      const rel = await getServerReliability(s.id)
      if (rel.data) setReliabilities(prev => ({ ...prev, [s.id]: rel.data }))
    } catch {}
  }

  const removeServer = (id: string) => {
    setSelected(prev => prev.filter(s => s.id !== id))
    setReliabilities(prev => { const n = { ...prev }; delete n[id]; return n })
  }

  const securityLabel: Record<string, string> = {
    verified: '🟢 安全认证', reviewed: '🟡 已审查',
    unreviewed: '🟠 未审查', blocked: '🔴 已阻止',
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">⚖️ Server 对比</h1>
        <p className="text-sm text-gray-500 mt-1">选择 2-4 个 MCP Server 进行并排对比</p>
      </div>

      {/* 搜索添加 */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex gap-2">
          <input type="text" value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
            placeholder="搜索 Server 名称..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none" />
          <button onClick={handleSearch} disabled={searching || selected.length >= maxSlots}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
            {searching ? '搜索中...' : '搜索'}
          </button>
        </div>
        {searchResults.length > 0 && (
          <div className="mt-3 space-y-1 max-h-48 overflow-y-auto">
            {searchResults.slice(0, 8).map(s => (
              <button key={s.id} onClick={() => addServer(s)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-blue-50 text-sm flex items-center justify-between">
                <span>{s.id}</span>
                <span className="text-xs text-blue-500">+ 添加对比</span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* 已选 Server */}
      {selected.length > 0 && (
        <div className="flex gap-2 flex-wrap">
          {selected.map(s => (
            <span key={s.id} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-100 text-blue-700 rounded-full text-sm">
              {s.id}
              <button onClick={() => removeServer(s.id)} className="text-blue-400 hover:text-blue-600 ml-1">✕</button>
            </span>
          ))}
          {selected.length < 2 && (
            <span className="text-xs text-gray-400 self-center">至少选择 2 个 Server 开始对比</span>
          )}
        </div>
      )}

      {/* 对比表格 */}
      {selected.length >= 2 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600 w-32">维度</th>
                {selected.map(s => (
                  <th key={s.id} className="text-left px-4 py-3 font-medium text-gray-900">
                    <div className="flex items-center justify-between">
                      <span className="truncate max-w-[200px]">{s.id.split('/').pop()}</span>
                      <button onClick={() => removeServer(s.id)} className="text-gray-300 hover:text-red-400 ml-2">✕</button>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {/* 基本信息 */}
              <tr className="border-b border-gray-100">
                <td className="px-4 py-2.5 text-gray-500">描述</td>
                {selected.map(s => (
                  <td key={s.id} className="px-4 py-2.5 text-gray-700 text-xs">{s.description?.slice(0, 120) || '-'}</td>
                ))}
              </tr>
              <tr className="border-b border-gray-100">
                <td className="px-4 py-2.5 text-gray-500">作者</td>
                {selected.map(s => <td key={s.id} className="px-4 py-2.5">{s.author || '-'}</td>)}
              </tr>
              {COMPARE_DIMENSIONS.map(dim => (
                <tr key={dim.key} className="border-b border-gray-100">
                  <td className="px-4 py-2.5 text-gray-500">{dim.label}</td>
                  {selected.map(s => {
                    const val = dim.key === 'security_level'
                      ? securityLabel[(s as any)[dim.key]] || (s as any)[dim.key]
                      : (s as any)[dim.key]
                    return (
                      <td key={s.id} className="px-4 py-2.5 font-medium">
                        {dim.format(val)}
                      </td>
                    )
                  })}
                </tr>
              ))}
              {/* 可靠性 */}
              <tr className="border-b border-gray-100">
                <td className="px-4 py-2.5 text-gray-500">可靠性评分</td>
                {selected.map(s => (
                  <td key={s.id} className="px-4 py-2.5">
                    {reliabilities[s.id] ? (
                      <span className={`font-medium ${
                        reliabilities[s.id].reliability_score >= 90 ? 'text-green-600' :
                        reliabilities[s.id].reliability_score >= 60 ? 'text-yellow-600' : 'text-red-600'
                      }`}>
                        {reliabilities[s.id].reliability_score}/100
                      </span>
                    ) : '-'}
                  </td>
                ))}
              </tr>
              {/* 分类 */}
              <tr className="border-b border-gray-100">
                <td className="px-4 py-2.5 text-gray-500">分类</td>
                {selected.map(s => (
                  <td key={s.id} className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {(s.categories || []).slice(0, 3).map(c => (
                        <span key={c} className="px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">{c}</span>
                      ))}
                    </div>
                  </td>
                ))}
              </tr>
              {/* 链接 */}
              <tr>
                <td className="px-4 py-2.5 text-gray-500">详情</td>
                {selected.map(s => (
                  <td key={s.id} className="px-4 py-2.5">
                    <Link to={`/servers/${encodeURIComponent(s.id)}`}
                      className="text-blue-600 hover:text-blue-800 text-xs">查看详情 →</Link>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}

      {/* 空态引导 */}
      {selected.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg mb-2">选择 Server 开始对比</p>
          <p className="text-sm">在上方搜索框中输入 Server 名称，添加到对比列表</p>
        </div>
      )}
    </div>
  )
}
