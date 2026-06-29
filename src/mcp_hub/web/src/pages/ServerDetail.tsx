import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  getServer, installServer, startServer, stopServer, rateServer, favoriteServer,
  apiGet, ServerInfo, SecurityScanResult, TokenAnalysisResult,
  scanServerSecurity, analyzeServerTokens, getServerReliability,
} from '../api/client'
import StatusBadge from '../components/StatusBadge'
import StarRating from '../components/StarRating'

const AGENTS = [
  { id: 'claude-code', name: 'Claude Code', color: 'bg-green-100 text-green-800' },
  { id: 'cursor', name: 'Cursor', color: 'bg-purple-100 text-purple-800' },
  { id: 'codex', name: 'Codex', color: 'bg-blue-100 text-blue-800' },
  { id: 'trae', name: 'Trae', color: 'bg-orange-100 text-orange-800' },
  { id: 'generic', name: '通用 mcp.json', color: 'bg-gray-100 text-gray-800' },
]

function SecurityBadge({ level }: { level: string }) {
  const config: Record<string, { icon: string; label: string; color: string }> = {
    verified: { icon: '🟢', label: '安全认证', color: 'text-green-700 bg-green-50 border-green-200' },
    reviewed: { icon: '🟡', label: '已审查', color: 'text-yellow-700 bg-yellow-50 border-yellow-200' },
    unreviewed: { icon: '🟠', label: '未审查', color: 'text-orange-700 bg-orange-50 border-orange-200' },
    blocked: { icon: '🔴', label: '危险', color: 'text-red-700 bg-red-50 border-red-200' },
  }
  const c = config[level] || { icon: '❓', label: level, color: 'text-gray-500 bg-gray-50 border-gray-200' }
  return <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium border ${c.color}`}>{c.icon} {c.label}</span>
}

function formatTokens(count: number | undefined | null): string {
  if (count == null) return '-'
  if (count < 1000) return `${count} tokens`
  return `${(count / 1000).toFixed(1)}K tokens`
}

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

  // New feature states
  const [security, setSecurity] = useState<SecurityScanResult | null>(null)
  const [tokenAnalysis, setTokenAnalysis] = useState<TokenAnalysisResult | null>(null)
  const [reliability, setReliability] = useState<any>(null)
  const [extraLoading, setExtraLoading] = useState(true)

  useEffect(() => {
    if (!id) return
    const sid = decodeURIComponent(id)
    getServer(sid)
      .then(setServer)
      .catch(() => setMessage('加载失败'))
      .finally(() => setLoading(false))

    // Load extra data in parallel
    Promise.all([
      scanServerSecurity(sid).then(r => setSecurity(r.data)).catch(() => {}),
      analyzeServerTokens(sid).then(r => setTokenAnalysis(r.data)).catch(() => {}),
      getServerReliability(sid).then(r => setReliability(r.data)).catch(() => {}),
    ]).finally(() => setExtraLoading(false))
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

        {/* Security + Token row */}
        <div className="flex items-center gap-3 flex-wrap mb-4">
          <span className="text-sm text-gray-500">{securityLabels[server.security_level] || server.security_level}</span>
          {security && (
            <SecurityBadge level={security.level} />
          )}
          {tokenAnalysis && (
            <span className={`text-xs px-2 py-0.5 rounded-full border ${
              tokenAnalysis.context_pct > 16 ? 'text-red-600 bg-red-50 border-red-200' :
              tokenAnalysis.context_pct > 10 ? 'text-yellow-600 bg-yellow-50 border-yellow-200' :
              'text-gray-500 bg-gray-50 border-gray-200'
            }`}>
              📊 {formatTokens(tokenAnalysis.total_tokens)}
            </span>
          )}
          {security && (
            <span className={`text-xs font-medium ${security.score >= 90 ? 'text-green-600' : security.score >= 70 ? 'text-yellow-600' : security.score >= 50 ? 'text-orange-600' : 'text-red-600'}`}>
              🛡️ 安全评分 {security.score}/100
            </span>
          )}
        </div>

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

      {/* Security Details */}
      {security && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">🛡️</span>
            <h2 className="font-semibold text-gray-900">安全分析</h2>
          </div>
          <div className="flex items-center gap-3 mb-3">
            <div className={`text-2xl font-bold ${
              security.score >= 90 ? 'text-green-600' : security.score >= 70 ? 'text-yellow-600' : security.score >= 50 ? 'text-orange-600' : 'text-red-600'
            }`}>{security.score}</div>
            <SecurityBadge level={security.level} />
            {security.network_access && <span className="text-xs text-gray-500">🌐 需要网络访问</span>}
            {security.file_access && <span className="text-xs text-gray-500">📁 需要文件访问</span>}
          </div>
          {security.findings.length > 0 && (
            <div className="space-y-1.5">
              <p className="text-xs text-gray-400 font-medium">发现项 ({security.findings.length})</p>
              {security.findings.slice(0, 5).map((f, i) => (
                <div key={i} className={`text-xs p-2 rounded-lg ${
                  f.severity === 'critical' ? 'bg-red-50 text-red-700' :
                  f.severity === 'high' ? 'bg-orange-50 text-orange-700' :
                  f.severity === 'suspicious' ? 'bg-yellow-50 text-yellow-700' :
                  'bg-gray-50 text-gray-600'
                }`}>
                  {f.title}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Token Analysis */}
      {tokenAnalysis && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">📊</span>
            <h2 className="font-semibold text-gray-900">Token 消耗分析</h2>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-3">
            <div>
              <p className="text-2xl font-bold text-gray-900">{formatTokens(tokenAnalysis.total_tokens)}</p>
              <p className="text-xs text-gray-500">工具定义总计</p>
            </div>
            <div>
              <p className={`text-2xl font-bold ${(tokenAnalysis.context_pct ?? 0) > 16 ? 'text-red-600' : (tokenAnalysis.context_pct ?? 0) > 10 ? 'text-yellow-600' : 'text-green-600'}`}>
                {(tokenAnalysis.context_pct ?? 0).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500">上下文占比</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{tokenAnalysis.tool_count}</p>
              <p className="text-xs text-gray-500">工具数量</p>
            </div>
          </div>
          {tokenAnalysis.estimated && (
            <p className="text-xs text-yellow-600">⚠️ 此分析为估算值，实际消耗取决于 Server 的具体工具定义</p>
          )}
          {tokenAnalysis.suggestions.length > 0 && (
            <div className="mt-2 text-xs text-gray-500">
              {tokenAnalysis.suggestions.slice(0, 2).map((s, i) => (
                <p key={i} className="mb-1">{s}</p>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Reliability */}
      {reliability && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-2 mb-4">
            <span className="text-xl">📈</span>
            <h2 className="font-semibold text-gray-900">可靠性监控</h2>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-3">
            <div>
              <p className={`text-2xl font-bold ${reliability.reliability_score >= 90 ? 'text-green-600' : reliability.reliability_score >= 60 ? 'text-yellow-600' : 'text-red-600'}`}>
                {reliability.reliability_score}
              </p>
              <p className="text-xs text-gray-500">可靠性评分</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{reliability.total_checks}</p>
              <p className="text-xs text-gray-500">健康检查次数</p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {(() => { const u = reliability.uptime_stats?.find(u => u.window === '24h'); return u ? (u.uptime_pct != null ? u.uptime_pct.toFixed(1) : '-') : '-'; })()}%
              </p>
              <p className="text-xs text-gray-500">24h Uptime</p>
            </div>
          </div>
          {reliability.uptime_stats && reliability.uptime_stats.length > 0 && (
            <div className="flex gap-3 text-xs text-gray-500 mt-1">
              {reliability.uptime_stats.map((u: any) => (
                <span key={u.window} className={`px-2 py-0.5 rounded ${
                  u.uptime_pct >= 99 ? 'bg-green-50 text-green-700' :
                  u.uptime_pct >= 95 ? 'bg-yellow-50 text-yellow-700' :
                  u.total_checks > 0 ? 'bg-red-50 text-red-700' : 'bg-gray-50 text-gray-400'
                }`}>
                  {u.window}: {u.total_checks > 0 ? `${u.uptime_pct}%` : '-'}
                </span>
              ))}
            </div>
          )}
        </div>
      )}

      {/* SaaS: 本地使用 */}
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
        <StarRating
          rating={myRating || Math.round(server.rating)}
          interactive
          onChange={handleRate}
          size="lg"
          reviewCount={server.review_count}
        />
      </div>
    </div>
  )
}
