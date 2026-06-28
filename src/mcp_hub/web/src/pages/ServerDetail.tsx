import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getServer, installServer, startServer, stopServer, rateServer, favoriteServer, apiGet, ServerInfo } from '../api/client'
import StatusBadge from '../components/StatusBadge'

const AGENTS = [
  { id: 'claude-code', name: 'Claude Code', color: 'bg-green-100 text-green-800' },
  { id: 'cursor', name: 'Cursor', color: 'bg-purple-100 text-purple-800' },
  { id: 'codex', name: 'Codex', color: 'bg-blue-100 text-blue-800' },
  { id: 'trae', name: 'Trae', color: 'bg-orange-100 text-orange-800' },
  { id: 'generic', name: '通用 mcp.json', color: 'bg-gray-100 text-gray-800' },
]

export default function ServerDetail() {
  const { id } = useParams<{ id: string }>()
  const [server, setServer] = useState<ServerInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [myRating, setMyRating] = useState(0)
  const [showConfig, setShowConfig] = useState(false)
  const [configData, setConfigData] = useState<any>(null)
  const [selectedAgent, setSelectedAgent] = useState('claude-code')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    if (!id) return
    getServer(decodeURIComponent(id))
      .then(setServer)
      .catch(() => setMessage('加载失败'))
      .finally(() => setLoading(false))
  }, [id])

  const fetchConfig = async (agentId: string) => {
    if (!id) return
    const sid = decodeURIComponent(id)
    const res = await apiGet<any>(`/servers/${encodeURIComponent(sid)}/config?agent=${agentId}`)
    if (res.data) setConfigData(res.data)
    setShowConfig(true)
  }

  const handleCopy = () => {
    if (!configData) return
    navigator.clipboard.writeText(JSON.stringify(configData.config_content, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (!server) return <div className="text-center py-16 text-gray-400">Server 未找到</div>

  const handleInstall = async () => {
    const r = await installServer(server.id)
    setMessage(r.message || r.data?.detail || '安装完成')
    if (r.success) {
      setServer({ ...server, status: 'stopped' })
      if (r.data?.configs) {
        const agentCfg = r.data.configs.find((c: any) =>
          c.agent === AGENTS.find(a => a.id === selectedAgent)?.name
        )
        setConfigData(agentCfg || r.data.configs[0])
        setShowConfig(true)
      }
    }
  }

  const handleStart = async () => {
    const r = await startServer(server.id)
    setMessage(r.message || '已启动')
    if (r.success) setServer({ ...server, status: 'running' })
  }

  const handleStop = async () => {
    const r = await stopServer(server.id)
    setMessage(r.message || '已停止')
    if (r.success) setServer({ ...server, status: 'stopped' })
  }

  const handleUninstall = async () => {
    if (!window.confirm('确定要卸载吗？')) return
    const res = await fetch(`/api/v1/servers/${encodeURIComponent(server.id)}/uninstall`, { method: 'POST' })
    const r = await res.json()
    setMessage(r.message || '已卸载')
    if (r.success) {
      setServer({ ...server, status: 'not_installed' })
      setShowConfig(false)
    }
  }

  const handleRate = async (rating: number) => {
    await rateServer(server.id, rating)
    setMyRating(rating)
    setMessage(`评分 ${rating}⭐ 成功`)
  }

  const handleFavorite = async () => {
    const r = await favoriteServer(server.id)
    setMessage(r.favorited ? '已收藏' : '已取消收藏')
  }

  const stars = '⭐'.repeat(Math.round(server.rating))
  const securityLabels: Record<string, string> = {
    verified: '🔒 安全认证',
    reviewed: '⚪ 已审查',
    unreviewed: '⚠️ 未审查',
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">← 返回市场</Link>

      {/* Header */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{server.id}</h1>
            <p className="text-sm text-gray-400 mt-1">v{server.version || '?'}</p>
          </div>
          <StatusBadge status={server.status} />
        </div>

        <p className="text-gray-600 mb-4">{server.description || '暂无描述'}</p>

        <div className="flex items-center gap-4 text-sm text-gray-500 mb-4">
          <span>{stars} {server.rating}</span>
          <span>💬 {server.review_count} 评价</span>
          <span>📥 {server.download_count} 次下载</span>
          <span>📄 {server.license}</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap mb-4">
          {server.categories?.map((cat) => (
            <span key={cat} className="px-2.5 py-1 bg-blue-50 text-blue-600 rounded text-xs font-medium">{cat}</span>
          ))}
        </div>

        <p className="text-sm text-gray-500 mb-4">{securityLabels[server.security_level] || server.security_level}</p>

        {/* Actions */}
        <div className="flex items-center gap-3 flex-wrap">
          {server.status === 'not_installed' && (
            <button onClick={handleInstall} className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors">
              📥 一键安装
            </button>
          )}
          {server.status === 'stopped' && (
            <button onClick={handleStart} className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium transition-colors">
              ▶️ 启动
            </button>
          )}
          {server.status === 'running' && (
            <button onClick={handleStop} className="px-6 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 font-medium transition-colors">
              ⏹ 停止
            </button>
          )}
          {(server.status === 'stopped' || server.status === 'running') && (
            <button onClick={handleUninstall} className="px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition-colors">
              🗑 卸载
            </button>
          )}
          <button onClick={handleFavorite} className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
            ⭐ 收藏
          </button>
          {server.homepage && (
            <a href={server.homepage} target="_blank" rel="noopener noreferrer" className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm">
              🔗 GitHub
            </a>
          )}
        </div>

        {message && (
          <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">{message}</div>
        )}
      </div>

      {/* SaaS: 本地使用 — 不需要部署 Hub */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-2xl">📋</span>
          <h2 className="font-semibold text-gray-900">本地使用（无需部署）</h2>
        </div>
        <p className="text-sm text-gray-500 mb-3">
          不想部署 MCP Hub？直接复制以下配置到你本地的 Agent 配置文件即可使用。
        </p>
        <div className="flex items-center gap-2 mb-3">
          {['Claude Code', 'Cursor', 'Codex', 'Trae'].map((agent) => (
            <button
              key={agent}
              onClick={() => { setSelectedAgent(agent.toLowerCase().replace(' ', '-')); fetchConfig(agent.toLowerCase().replace(' ', '-')) }}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${
                selectedAgent === agent.toLowerCase().replace(' ', '-')
                  ? 'bg-blue-100 text-blue-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}
            >
              {agent}
            </button>
          ))}
        </div>
        {configData && (
          <div className="space-y-2">
            <p className="text-xs text-gray-400">
              添加到 <code className="bg-gray-100 px-1 rounded">{configData.config_path}</code>
            </p>
            <div className="bg-gray-900 rounded-lg p-4 overflow-x-auto">
              <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap">
                {JSON.stringify(configData.config_content, null, 2)}
              </pre>
            </div>
            <button
              onClick={() => { navigator.clipboard.writeText(JSON.stringify(configData.config_content, null, 2)); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
              className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm"
            >
              {copied ? '✅ 已复制!' : '📋 复制配置'}
            </button>
          </div>
        )}
      </div>

      {/* Multi-Agent Config */}
      {(server.status === 'stopped' || server.status === 'running') && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">🔌 接入你本地的 Agent</h2>
          </div>
          <p className="text-sm text-gray-500 mb-3">
            选择你的 Agent 类型，复制配置到本地对应文件即可。
            Hub 运行在服务器上，无法自动写入你本地的配置文件。
          </p>

          <div className="flex items-center gap-2 mb-4">
            {AGENTS.map((a) => (
              <button
                key={a.id}
                onClick={() => { setSelectedAgent(a.id); fetchConfig(a.id) }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  selectedAgent === a.id ? a.color : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                {a.name}
              </button>
            ))}
          </div>

          {showConfig && configData && (
            <div className="space-y-3">
              <p className="text-sm text-gray-500">
                将以下 JSON 添加到 <code className="bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">{configData.config_path}</code>
              </p>
              <div className="relative bg-gray-900 rounded-lg p-4 overflow-x-auto">
                <pre className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                  {JSON.stringify(configData.config_content, null, 2)}
                </pre>
              </div>
              <button
                onClick={handleCopy}
                className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 transition-colors text-sm"
              >
                {copied ? '✅ 已复制!' : '📋 复制配置'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Rating */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-3">评分</h2>
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map((n) => (
            <button
              key={n}
              onClick={() => handleRate(n)}
              className={`text-2xl transition-colors ${n <= (myRating || Math.round(server.rating)) ? '' : 'grayscale opacity-40'}`}
            >
              ⭐
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
