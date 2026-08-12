import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  getServer, installServer, rateServer, favoriteServer,
  apiDelete, apiGet, apiPost, getAuthState, getFavoriteServers, ServerInfo, SecurityScanResult, TokenAnalysisResult,
  scanServerSecurity, analyzeServerTokens, getServerReliability,
} from '../api/client'
import StarRating from '../components/StarRating'
import InfoTooltip from '../components/InfoTooltip'
import { copyStatus, copyText } from '../utils/clipboard'

const AGENTS = [
  { id: 'claude-code', name: 'Claude Code', color: 'bg-green-100 text-green-800' },
  { id: 'claude-desktop', name: 'Claude Desktop', color: 'bg-emerald-100 text-emerald-800' },
  { id: 'cursor', name: 'Cursor', color: 'bg-purple-100 text-purple-800' },
  { id: 'vscode-copilot', name: 'VS Code Copilot', color: 'bg-sky-100 text-sky-800' },
  { id: 'codex', name: 'Codex', color: 'bg-blue-100 text-blue-800' },
  { id: 'trae', name: 'Trae', color: 'bg-orange-100 text-orange-800' },
  { id: 'windsurf', name: 'Windsurf', color: 'bg-cyan-100 text-cyan-800' },
  { id: 'generic', name: '通用 mcp.json', color: 'bg-gray-100 text-gray-800' },
]

interface CompatibilityObservation {
  device_name: string
  agent_type: string
  transport: string
  protocol_version: string
  capabilities: string[]
  running: boolean
  compatibility: {
    status: 'verified' | 'partial' | 'unsupported'
    reason: string
    features: {
      tools: boolean
      resources: boolean
      prompts: boolean
      tasks: boolean
    }
  }
}

interface InventoryResponse {
  devices: Array<{
    name: string
    agent_type: string
    servers: Array<{
      server_name: string
      market_server_id: string | null
      transport: string
      protocol_version: string
      capabilities: string[]
      running: boolean
      compatibility: CompatibilityObservation['compatibility']
    }>
  }>
}

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

function compatibilityLabel(status: CompatibilityObservation['compatibility']['status']): string {
  if (status === 'verified') return '已验证'
  if (status === 'partial') return '部分支持'
  return '不支持'
}

function compatibilityClass(status: CompatibilityObservation['compatibility']['status']): string {
  if (status === 'verified') return 'border-green-200 bg-green-50 text-green-700'
  if (status === 'partial') return 'border-amber-200 bg-amber-50 text-amber-700'
  return 'border-red-200 bg-red-50 text-red-700'
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
  const [isFavorited, setIsFavorited] = useState(false)
  const [installing, setInstalling] = useState(false)

  // New feature states
  const [security, setSecurity] = useState<SecurityScanResult | null>(null)
  const [tokenAnalysis, setTokenAnalysis] = useState<TokenAnalysisResult | null>(null)
  const [reliability, setReliability] = useState<any>(null)
  const [recommendations, setRecommendations] = useState<ServerInfo[]>([])
  const [compatibilityObservations, setCompatibilityObservations] = useState<CompatibilityObservation[]>([])

  // Review states
  const [reviews, setReviews] = useState<any[]>([])
  const [reviewText, setReviewText] = useState('')
  const [reviewRating, setReviewRating] = useState(5)
  const [submittingReview, setSubmittingReview] = useState(false)
  const [replyTo, setReplyTo] = useState<any>(null)
  const { token, userId } = getAuthState()
  const currentUser = userId || ''

  // 追踪状态来自当前账户的服务端记录，不使用浏览器缓存作为账户数据。
  const [isTracked, setIsTracked] = useState(false)
  useEffect(() => {
    if (!id) return
    const sid = decodeURIComponent(id)
    if (token) {
      apiGet<any[]>('/config/user-servers')
        .then(result => {
          const found = (result.data || []).some((server: any) => (
            server.name === sid || server.hub_id === sid
          ))
          setIsTracked(found)
        })
        .catch(() => setIsTracked(false))
    } else {
      setIsTracked(false)
    }
    if (token) {
      getFavoriteServers()
        .then(result => setIsFavorited((result.data || []).some(server => server.id === sid)))
        .catch(() => setIsFavorited(false))
    } else {
      setIsFavorited(false)
    }
  }, [id, token])

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
      apiGet<any[]>(`/community/reviews/${encodeURIComponent(sid)}`).then(r => setReviews(r.data || [])).catch(() => {}),
      apiGet<ServerInfo[]>(`/market/recommendations?server_id=${encodeURIComponent(sid)}&limit=4`).then(r => setRecommendations(r.data || [])).catch(() => {}),
      // Auto-fetch config for first agent
      apiGet<any>(`/servers/${encodeURIComponent(sid)}/config?agent=claude-code`)
        .then(r => { if (r.data) { setConfigData(r.data); setShowConfig(true) }})
        .catch(() => {}),
    ])
  }, [id])

  useEffect(() => {
    if (!server || !token) {
      setCompatibilityObservations([])
      return
    }
    let active = true
    void apiGet<InventoryResponse>('/telemetry/inventory')
      .then(result => {
        if (!active) return
        const observations = (result.data?.devices || []).flatMap(device => (
          device.servers
            .filter(observed => (
              observed.market_server_id === server.id
            ))
            .map(observed => ({
              device_name: device.name,
              agent_type: device.agent_type,
              transport: observed.transport,
              protocol_version: observed.protocol_version,
              capabilities: observed.capabilities,
              running: observed.running,
              compatibility: observed.compatibility,
            }))
        ))
        setCompatibilityObservations(observations)
      })
      .catch(() => {
        if (active) setCompatibilityObservations([])
      })
    return () => {
      active = false
    }
  }, [server, token])

  const latestAgentRef = useRef<string>('')
  const reviewInputRef = useRef<HTMLTextAreaElement>(null)

  const fetchConfig = async (agentId: string) => {
    if (!id) return
    const sid = decodeURIComponent(id)
    latestAgentRef.current = agentId
    try {
      const res = await apiGet<any>(`/servers/${encodeURIComponent(sid)}/config?agent=${agentId}`)
      // 防止竞态：只应用最后请求的 agent 的结果
      if (latestAgentRef.current === agentId && res.data) {
        setConfigData(res.data)
      }
      setShowConfig(true)
    } catch (e) {
      console.error('Config fetch failed:', e)
    }
  }

  const handleCopy = async () => {
    if (!configData) return
    const configText = configData.config_text || JSON.stringify(configData.config_content, null, 2)
    const didCopy = await copyText(configText)
    setCopied(didCopy)
    if (!didCopy) {
      setMessage(copyStatus(false, ''))
      setTimeout(() => setMessage(''), 4000)
    }
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (!server) return <div className="text-center py-16 text-gray-400">Server 未找到</div>

  const handleInstall = async () => {
    setInstalling(true)
    setMessage('')
    try {
      const r = await installServer(server.id)
      if (!r.success) {
        setMessage(`❌ 追踪失败: ${r.message || r.data?.detail || '未知错误'}`)
        return
      }
      setMessage(`✅ 已加入追踪列表。本地安装命令: ${r.data?.install_command || r.message || '请查看项目文档'}`)
      setIsTracked(true)
      if (r.data?.configs) {
        const agentCfg = r.data.configs.find((c: any) =>
          c.agent === AGENTS.find(a => a.id === selectedAgent)?.name
        )
        setConfigData(agentCfg || r.data.configs[0])
        setShowConfig(true)
      }
    } catch (e: any) {
      setMessage(`追踪失败: ${e.message || '未知错误'}`)
    } finally {
      setInstalling(false)
    }
  }

  const handleUntrack = async () => {
    if (!window.confirm('确定要停止追踪此 Server 吗？这不会卸载你本地已经安装的依赖。')) return
    try {
      await apiDelete(`/config/user-servers/${encodeURIComponent(server.id)}`)
      setIsTracked(false)
      setMessage('已停止追踪此 Server')
    } catch {
      setMessage('停止追踪失败，请稍后重试')
    }
  }

  const handleRate = async (rating: number) => {
    try {
      await rateServer(server.id, rating)
      setMyRating(rating)
      setMessage(`评分 ${rating}⭐ 成功`)
      try {
        const r = await apiGet<any[]>(`/community/reviews/${encodeURIComponent(server.id)}`)
        if (r.data) setReviews(r.data)
      } catch {}
    } catch (e: any) {
      setMessage(`评分失败: ${e.message || '未知错误'}`)
    }
  }

  const handleFavorite = async () => {
    try {
      const r = await favoriteServer(server.id)
      const favd = r.favorited
      setIsFavorited(favd)
      setMessage(favd ? '⭐ 已收藏' : '已取消收藏')
    } catch (e: any) {
      setMessage(`收藏操作失败: ${e.message || '未知错误'}`)
    }
  }

  const handleSubmitReview = async () => {
    if (!reviewText.trim()) { setMessage('请填写评价内容'); return }
    setSubmittingReview(true)
    try {
      const body: any = { server_id: server.id, rating: reviewRating, content: reviewText.trim() }
      if (replyTo) body.parent_id = replyTo.id
      const r = await apiPost<any>('/community/rate', body)
      if (r.success) {
        setMessage('✅ 评价已提交')
        setReviewText('')
        setReviewRating(5)
        setReplyTo(null)
        // Reload reviews
        const r2 = await apiGet<any[]>(`/community/reviews/${encodeURIComponent(server.id)}`)
        if (r2.data) setReviews(r2.data)
      } else {
        setMessage('❌ ' + (r.message || '提交失败'))
      }
    } catch (e: any) { setMessage('❌ ' + (e?.message || '网络错误，请检查是否已登录')) }
    finally { setSubmittingReview(false) }
  }

  const handleDeleteReview = async (reviewId: number) => {
    if (!window.confirm('确定要删除此评价吗？')) return
    try {
      const r: any = await apiPost<any>(`/community/review/delete/${reviewId}`)
      if (r.success) {
        setReviews(reviews.filter(r => r.id !== reviewId))
        setMessage('✅ 评价已删除')
      } else {
        setMessage('❌ ' + (r.error || '删除失败'))
      }
    } catch { setMessage('❌ 网络错误') }
  }

  function fmtNum(n: number): string { return n >= 1000 ? `${(n / 1000).toFixed(1).replace('.0', '')}K` : String(n) }
  const securityLabels: Record<string, string> = {
    verified: '🔒 安全认证',
    reviewed: '⚪ 已审查',
    unreviewed: '⚠️ 未审查',
    blocked: '🚫 已阻止',
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
          <span className="rounded-md border border-gray-200 bg-gray-50 px-2 py-1 text-xs text-gray-600">
            市场条目
          </span>
        </div>

        <p className="text-gray-600 mb-4">{server.description || '暂无描述'}</p>

        <div className="flex items-center gap-4 text-sm text-gray-500 mb-4">
          <span><StarRating rating={server.rating} size="sm" showValue /></span>
          <span>💬 {server.review_count} 评价</span>
          <span>📥 {fmtNum(server.download_count)} 次下载</span>
          <span>📄 {server.license}</span>
        </div>

        <div className="flex items-center gap-2 flex-wrap mb-4">
          {server.categories?.map((cat) => (
            <span key={cat} className="px-2.5 py-1 bg-blue-50 text-blue-600 rounded text-xs font-medium">{cat}</span>
          ))}
        </div>

        {/* Security + Token row */}
        <div className="flex items-center gap-3 flex-wrap mb-4">
          <span className="text-sm text-gray-500">
            <InfoTooltip description="市场安全状态基于发布信息和安全扫描；它提示已知风险，但不能替代在你的运行环境中进行的审查。">
              {securityLabels[server.security_level] || server.security_level}
            </InfoTooltip>
          </span>
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
              🛡️ <InfoTooltip description="安全扫描根据命令、依赖来源、发布者和代码模式等信号计算的 0-100 分风险提示，不是绝对安全保证。">安全评分</InfoTooltip> {security.score}/100
            </span>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center gap-3 flex-wrap">
          {!isTracked && (
            <button onClick={handleInstall} disabled={installing}
              className={`px-6 py-2 rounded-lg font-medium transition-colors ${installing ? 'bg-gray-400 text-white cursor-not-allowed' : 'bg-blue-600 text-white hover:bg-blue-700'}`}>
              {installing ? '⏳ 保存中...' : '＋ 加入追踪'}
            </button>
          )}
          {isTracked && (
            <span className="rounded-md border border-green-200 bg-green-50 px-4 py-2 text-sm font-medium text-green-800">
              已追踪
            </span>
          )}
          {isTracked && (
            <button onClick={handleUntrack} className="px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 transition-colors">
              停止追踪
            </button>
          )}
          <button onClick={handleFavorite} className={`px-4 py-2 border rounded-lg transition-colors ${isFavorited ? 'bg-yellow-50 border-yellow-300 text-yellow-700' : 'border-gray-300 hover:bg-gray-50'}`}>
            {isFavorited ? '⭐ 已收藏' : '☆ 收藏'}
          </button>
          {server.homepage && (
            /^https?:\/\//i.test(server.homepage) ? (
              <a href={server.homepage} target="_blank" rel="noopener noreferrer" className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm">
                🔗 GitHub
              </a>
            ) : (
              <span className="px-4 py-2 border border-gray-300 rounded-lg text-sm text-gray-400">
                🔗 {server.homepage}
              </span>
            )
          )}
        </div>

        {message && (
          <div className="mt-4 p-3 bg-blue-50 text-blue-700 rounded-lg text-sm">{message}</div>
        )}
      </div>

      {/* 原生本地安装命令 */}
      {(server as any).install_command && (
        <div className="bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 rounded-xl p-5 mb-6 border border-blue-200 dark:border-blue-800">
          <h3 className="font-semibold text-lg mb-2">🚀 本地安装命令</h3>
          <p className="text-sm text-gray-600 mb-3">
            此命令只负责在你的电脑准备 Server。需要监控时，还必须在监控页创建设备并完成 Gateway 接入。
          </p>

          {/* 命令复制区 */}
          <div className="flex items-center gap-2 mb-4">
            <code className="flex-1 bg-gray-900 text-green-400 px-4 py-2.5 rounded-lg text-sm font-mono overflow-x-auto">
              {(server as any).install_command || ''}
            </code>
            <button
              onClick={async () => {
                const cmd = (server as any).install_command || ''
                if (cmd) {
                  const didCopy = await copyText(cmd)
                  setCopied(didCopy)
                  if (!didCopy) {
                    setMessage(copyStatus(false, ''))
                    setTimeout(() => setMessage(''), 4000)
                  }
                  setTimeout(() => setCopied(false), 2000)
                }
              }}
              className="px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm font-medium whitespace-nowrap transition-colors"
            >
              {copied ? '✅ 已复制' : '📋 复制命令'}
            </button>
          </div>

          <div className="text-xs text-gray-400 mt-3">
            执行第三方命令前，请先核对项目主页、依赖来源和所需权限。
          </div>
        </div>
      )}

      {token && (
        <section className="border border-gray-200 bg-white p-6">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <div>
              <h2 className="font-semibold text-gray-900">本地 MCP 协议兼容性</h2>
              <p className="mt-1 text-sm text-gray-500">
                仅显示你的 Gateway 已实际协商的协议和能力，不会读取参数、环境变量值或请求内容。
              </p>
            </div>
            <Link to="/local" className="text-sm font-medium text-blue-700 hover:underline">
              查看全部本地清单
            </Link>
          </div>
          {compatibilityObservations.length === 0 ? (
            <p className="mt-4 text-sm text-gray-500">
              当前没有与此市场条目精确匹配的本地 Gateway 观测记录。
            </p>
          ) : (
            <div className="mt-4 divide-y divide-gray-100 border border-gray-200">
              {compatibilityObservations.map((observation, index) => (
                <div
                  key={`${observation.device_name}-${observation.agent_type}-${index}`}
                  className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3 text-sm"
                >
                  <div className="min-w-40 flex-1">
                    <p className="font-medium text-gray-800">
                      {observation.agent_type} · {observation.device_name}
                    </p>
                    <p className="mt-0.5 text-xs text-gray-500">
                      MCP {observation.protocol_version || '未协商'} · {observation.transport} ·
                      {observation.running ? ' 运行中' : ' 未运行'}
                    </p>
                  </div>
                  <span
                    className={`border px-2 py-0.5 text-xs ${compatibilityClass(observation.compatibility.status)}`}
                    title={observation.compatibility.reason}
                  >
                    {compatibilityLabel(observation.compatibility.status)}
                  </span>
                  <span className="text-xs text-gray-500">
                    工具 {observation.compatibility.features.tools ? '支持' : '未声明'} ·
                    资源 {observation.compatibility.features.resources ? '支持' : '未声明'} ·
                    提示词 {observation.compatibility.features.prompts ? '支持' : '未声明'} ·
                    任务 {observation.compatibility.features.tasks ? '支持' : '暂不支持'}
                  </span>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

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
            <h2 className="font-semibold text-gray-900">工具定义 Token 估算</h2>
          </div>
          <div className="grid grid-cols-3 gap-4 mb-3">
            <div>
              <p className="text-2xl font-bold text-gray-900">{formatTokens(tokenAnalysis.total_tokens)}</p>
              <p className="text-xs text-gray-500"><InfoTooltip description="将此 Server 的工具名称、描述和输入参数定义编码后估算的 Token 数量。">工具定义总计</InfoTooltip></p>
            </div>
            <div>
              <p className={`text-2xl font-bold ${(tokenAnalysis.context_pct ?? 0) > 16 ? 'text-red-600' : (tokenAnalysis.context_pct ?? 0) > 10 ? 'text-yellow-600' : 'text-green-600'}`}>
                {(tokenAnalysis.context_pct ?? 0).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500"><InfoTooltip description="工具定义估算 Token 占 128K 上下文窗口的比例，用于判断工具描述是否过于冗长。">上下文占比</InfoTooltip></p>
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
              <p className="text-xs text-gray-500"><InfoTooltip description="依据已记录的健康检查计算的 0-100 分指标；没有检查记录时不应将低分解释为不可靠。">可靠性评分</InfoTooltip></p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">{reliability.total_checks}</p>
              <p className="text-xs text-gray-500"><InfoTooltip description="Hub 对该 Server 执行并记录的健康检查次数。">健康检查次数</InfoTooltip></p>
            </div>
            <div>
              <p className="text-2xl font-bold text-gray-900">
                {(() => { const u = (reliability.uptime_stats as any[])?.find((u: any) => u.window === '24h'); return u ? (u.uptime_pct != null ? u.uptime_pct.toFixed(1) : '-') : '-'; })()}%
              </p>
              <p className="text-xs text-gray-500"><InfoTooltip description="过去 24 小时健康检查中成功的比例；没有检查记录时显示“-”。">24h Uptime</InfoTooltip></p>
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

      {/* Reviews */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">💬</span>
          <h2 className="font-semibold text-gray-900">评价</h2>
        </div>

        {/* Review list */}
        <div className="space-y-3 mb-6">
          {reviews.length === 0 ? (
            <p className="text-sm text-gray-400">暂无评价，来写第一条吧！</p>
          ) : (
            reviews.map((r: any) => (
              <div key={r.id}>
                <div className="p-3 bg-gray-50 rounded-lg">
                  <div className="flex items-center justify-between mb-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-700">{r.user_id}</span>
                      <span className="text-xs">{'★'.repeat(r.rating)}{'☆'.repeat(5 - r.rating)}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-400">{r.created_at?.slice(0, 10)}</span>
                      {r.user_id === currentUser && (
                        <button onClick={() => handleDeleteReview(r.id)} className="text-xs text-red-500 hover:text-red-700">删除</button>
                      )}
                    </div>
                  </div>
                  {r.content && <p className="text-sm text-gray-600 mb-2">{r.content}</p>}
                  <button onClick={() => {
                    setReplyTo(r)
                    reviewInputRef.current?.focus()
                  }} className="text-xs text-blue-500 hover:text-blue-700">↩ 回复</button>

                  {/* Replies */}
                  {r.replies && r.replies.length > 0 && (
                    <div className="ml-4 mt-2 pl-3 border-l-2 border-gray-200 space-y-2">
                      {r.replies.map((reply: any) => (
                        <div key={reply.id} className="p-2 bg-white rounded">
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-medium text-gray-600">{reply.user_id}</span>
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-gray-400">{reply.created_at?.slice(0, 10)}</span>
                              {reply.user_id === currentUser && (
                                <button onClick={() => handleDeleteReview(reply.id)} className="text-xs text-red-500">删除</button>
                              )}
                            </div>
                          </div>
                          <p className="text-sm text-gray-600 mt-0.5">{reply.content}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Review form */}
        <div className="border-t border-gray-100 pt-4">
          <p className="text-sm font-medium text-gray-700 mb-2">
            {replyTo ? `↩ 回复 ${replyTo.user_id}` : '写评价'}
            {replyTo && <button onClick={() => setReplyTo(null)} className="ml-2 text-xs text-gray-400 hover:text-gray-600">取消回复</button>}
          </p>
          <div className="flex items-center gap-1 mb-3">
            {[1,2,3,4,5].map(n => (
              <button key={n} onClick={() => setReviewRating(n)}
                className={`text-xl ${n <= reviewRating ? '' : 'opacity-30'}`}>★</button>
            ))}
          </div>
          <textarea ref={reviewInputRef} value={reviewText} onChange={e => setReviewText(e.target.value)}
            placeholder="分享你的使用体验..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none" />
          <button onClick={handleSubmitReview} disabled={submittingReview || !reviewText.trim()}
            className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {submittingReview ? '提交中...' : replyTo ? '提交回复' : '提交评价'}
          </button>
        </div>
      </div>

      {/* Gateway monitoring boundary */}
      <div className="border-l-4 border-blue-500 bg-blue-50 px-4 py-3 text-sm text-blue-900">
        加入追踪只保存当前账户与 Server 的关系，不会远程安装或启动进程。Agent 直接连接 Server 时不会产生 Hub 监控数据；
        需要监控请在“监控”页创建设备并运行 <code className="mx-1 font-mono text-xs">mcp-hub agent setup</code>。
      </div>

      {(
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-gray-900">🔌 原生直连配置（不含监控）</h2>
          </div>
          <p className="text-sm text-gray-500 mb-3">
            选择 Agent 后，将配置合并到本地对应文件。该方式绕过 Gateway，适合不需要统一调用监控的场景。
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
                将以下 {(configData.config_format || 'json').toUpperCase()} 合并到
                <code className="ml-1 bg-gray-100 px-1.5 py-0.5 rounded text-xs font-mono">{configData.config_path}</code>
              </p>
              <div className="relative bg-gray-900 rounded-lg p-4 overflow-x-auto">
                <pre className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                  {configData.config_text || JSON.stringify(configData.config_content, null, 2)}
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

      {/* 同类推荐 */}
      {recommendations.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">🔗 同类推荐</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {recommendations.map(rec => (
              <Link key={rec.id} to={`/servers/${encodeURIComponent(rec.id)}`}
                className="p-3 bg-gray-50 rounded-lg hover:bg-blue-50 transition-colors border border-transparent hover:border-blue-200">
                <p className="text-sm font-medium text-gray-800 truncate">{rec.id.split('/').pop()}</p>
                <div className="flex items-center gap-2 mt-1 text-xs text-gray-400">
                  <span>⭐ {rec.rating?.toFixed(1) || '-'}</span>
                  <span>📥 {rec.download_count >= 1000 ? `${(rec.download_count/1000).toFixed(1)}K` : rec.download_count}</span>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* MCP 工具 Playground */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center gap-2 mb-4">
          <span className="text-xl">🧪</span>
          <h2 className="font-semibold text-gray-900">工具测试台</h2>
        </div>
        <p className="text-sm text-gray-500 mb-3">
          查看标准 MCP 工具列表和调用格式。本页不会在 Hub 服务器上启动或直接调用此 Server。
        </p>
        <div className="bg-gray-900 rounded-lg p-4">
          <p className="text-green-400 text-xs font-mono mb-2"># 工具列表（JSON-RPC 2.0）</p>
          <pre className="text-gray-300 text-xs font-mono whitespace-pre-wrap">
{`// 获取工具列表
{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}

// 调用工具（示例）
{"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
  "name": "tool_name",
  "arguments": { "key": "value" }
}}`}
          </pre>
        </div>
        <div className="mt-3 flex gap-2">
          <button
            onClick={async () => {
              const cmd = (server as any).install_command || `npx ${server.name}`
              const didCopy = await copyText(
                `# 在本地终端运行此 Server 后，可通过 MCP 协议调用其工具\n${cmd}`
              )
              setMessage(copyStatus(didCopy, '✅ 命令已复制'))
              setTimeout(() => setMessage(''), 2000)
            }}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
            📋 复制本地启动命令
          </button>
          <a
            href={(server.homepage && /^https?:\/\//i.test(server.homepage)) ? server.homepage : `https://github.com/search?q=${encodeURIComponent(server.id)}`}
            target="_blank" rel="noopener noreferrer"
            className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200">
            📖 查看文档
          </a>
        </div>
      </div>

    </div>
  )
}
