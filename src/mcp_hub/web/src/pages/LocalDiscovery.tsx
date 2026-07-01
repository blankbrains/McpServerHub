import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet } from '../api/client'

interface AgentSummary {
  agent_id: string
  agent_name: string
  configured: boolean
  server_count: number
  servers: string[]
}

interface CompareItem {
  server_name: string
  present_in: string[]
  absent_in: string[]
  commands: Record<string, string>
  has_conflict: boolean
}

interface ConflictItem {
  server_name: string
  agent_a: string
  command_a: string
  agent_b: string
  command_b: string
  severity: string
}

interface DiscoverData {
  total_agents_known: number
  total_agents_found: number
  total_unique_servers: number
  agents: AgentSummary[]
}

export default function LocalDiscovery() {
  const [discover, setDiscover] = useState<DiscoverData | null>(null)
  const [compare, setCompare] = useState<CompareItem[]>([])
  const [conflicts, setConflicts] = useState<ConflictItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tab, setTab] = useState<'agents' | 'compare' | 'conflicts'>('agents')

  useEffect(() => {
    let failed = false
    Promise.all([
      apiGet<DiscoverData>('/local/discover').then(r => setDiscover(r.data)).catch(() => { failed = true }),
      apiGet<CompareItem[]>('/local/compare').then(r => setCompare(r.data || [])).catch(() => { failed = true }),
      apiGet<ConflictItem[]>('/local/conflicts').then(r => setConflicts(r.data || [])).catch(() => { failed = true }),
    ]).finally(() => {
      if (failed) setError('部分数据加载失败')
      setLoading(false)
    })
  }, [])

  if (loading) {
    return <div className="flex items-center justify-center h-64 text-gray-400">扫描本地 Agent 配置...</div>
  }

  if (error) {
    return (
      <div className="text-center py-16 text-red-500 space-y-3">
        <p>{error}</p>
        <p className="text-xs text-gray-400">本功能需要 Hub 在本地运行才能扫描 Agent 配置文件</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">🔍 本地 Agent 发现</h1>
        <p className="text-sm text-gray-500">
          发现 {discover?.total_agents_found || 0}/{discover?.total_agents_known || 0} 个 Agent ·
          {discover?.total_unique_servers || 0} 个 MCP Server
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 rounded-lg p-1 w-fit">
        {(['agents', 'compare', 'conflicts'] as const).map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}
            aria-pressed={tab === t}
          >
            {{ agents: 'Agent 总览', compare: '跨 Agent 对比', conflicts: `配置冲突${conflicts.length ? ` (${conflicts.length})` : ''}` }[t]}
          </button>
        ))}
      </div>

      {/* Agent 总览 Tab */}
      {tab === 'agents' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {(discover?.agents || []).map(agent => (
            <div key={agent.agent_id}
              className={`bg-white rounded-xl border p-5 ${agent.configured ? 'border-green-200' : 'border-gray-200 opacity-60'}`}>
              <div className="flex items-center justify-between mb-3">
                <h3 className="font-semibold text-gray-900">{agent.agent_name}</h3>
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${agent.configured ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {agent.configured ? `${agent.server_count} 个 Server` : '未检测到'}
                </span>
              </div>
              <p className="text-xs text-gray-500 mb-2 font-mono">{agent.agent_id}</p>
              {agent.servers.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {agent.servers.map(s => (
                    <span key={s} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">{s}</span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 跨 Agent 对比 Tab */}
      {tab === 'compare' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b border-gray-200">
                  <th className="p-3 text-left text-xs font-medium text-gray-500">Server</th>
                  <th className="p-3 text-left text-xs font-medium text-gray-500">已安装于</th>
                  <th className="p-3 text-left text-xs font-medium text-gray-500">缺失于</th>
                  <th className="p-3 text-left text-xs font-medium text-gray-500">状态</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {compare.length === 0 ? (
                  <tr><td colSpan={4} className="p-8 text-center text-gray-400">未检测到任何 Agent 配置</td></tr>
                ) : compare.map(item => (
                  <tr key={item.server_name} className="hover:bg-gray-50">
                    <td className="p-3 font-medium text-gray-900">{item.server_name}</td>
                    <td className="p-3">
                      <div className="flex flex-wrap gap-1">
                        {item.present_in.map(a => (
                          <span key={a} className="px-2 py-0.5 bg-green-50 text-green-600 rounded text-xs">{a}</span>
                        ))}
                      </div>
                    </td>
                    <td className="p-3">
                      <div className="flex flex-wrap gap-1">
                        {item.absent_in.map(a => (
                          <span key={a} className="px-2 py-0.5 bg-red-50 text-red-500 rounded text-xs">{a}</span>
                        ))}
                      </div>
                    </td>
                    <td className="p-3">
                      {item.has_conflict
                        ? <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs">⚠ 命令不一致</span>
                        : <span className="text-green-600 text-xs">✅ 一致</span>
                      }
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 配置冲突 Tab */}
      {tab === 'conflicts' && (
        <div className="space-y-3">
          {conflicts.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center text-gray-400">
              🎉 没有检测到配置冲突，各 Agent 配置一致
            </div>
          ) : conflicts.map((c, i) => (
            <div key={i} className="bg-white rounded-xl border border-yellow-200 p-5">
              <div className="flex items-center gap-2 mb-2">
                <span className="text-yellow-500">⚠️</span>
                <h3 className="font-semibold text-gray-900">{c.server_name}</h3>
                <span className="px-2 py-0.5 bg-yellow-100 text-yellow-700 rounded text-xs">{c.severity}</span>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">{c.agent_a}</p>
                  <code className="text-xs text-green-700 break-all">{c.command_a}</code>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">{c.agent_b}</p>
                  <code className="text-xs text-green-700 break-all">{c.command_b}</code>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
