import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  getServer, installServer, startServer, stopServer, rateServer, favoriteServer,
  apiGet, apiPost, ServerInfo, SecurityScanResult, TokenAnalysisResult,
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
  const [isFavorited, setIsFavorited] = useState(false)

  // New feature states
  const [security, setSecurity] = useState<SecurityScanResult | null>(null)
  const [tokenAnalysis, setTokenAnalysis] = useState<TokenAnalysisResult | null>(null)
  const [reliability, setReliability] = useState<any>(null)
  const [extraLoading, setExtraLoading] = useState(true)

  // Review states
  const [reviews, setReviews] = useState<any[]>([])
  const [reviewText, setReviewText] = useState('')
  const [reviewRating, setReviewRating] = useState(5)
  const [submittingReview, setSubmittingReview] = useState(false)
  const [replyTo, setReplyTo] = useState<any>(null)
  const currentUser = localStorage.getItem('mcp_hub_user') || 'anonymous'

  // 检查此 Server 是否已被用户追踪（上传配置/市场添加）
  const [isTracked, setIsTracked] = useState(false)
  useEffect(() => {
    if (!id) return
    const sid = decodeURIComponent(id)
    try {
      const myServers = JSON.parse(localStorage.getItem('mcp_hub_my_servers') || '[]')
      const found = myServers.some((x: any) => x.name === sid || x.hub_id === sid)
      setIsTracked(found)
      // 检查是否已收藏
      const favs = JSON.parse(localStorage.getItem('mcp_hub_favorites') || '[]')
      setIsFavorited(favs.includes(sid))
    } catch { setIsTracked(false) }
  }, [id])

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
      // Auto-fetch config for first agent
      apiGet<any>(`/servers/${encodeURIComponent(sid)}/config?agent=claude-code`)
        .then(r => { if (r.data) { setConfigData(r.data); setShowConfig(true) }})
        .catch(() => {}),
    ]).finally(() => setExtraLoading(false))
  }, [id])

  const latestAgentRef = useRef<string>('')

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

  const handleCopy = () => {
    if (!configData) return
    navigator.clipboard.writeText(JSON.stringify(configData.config_content, null, 2))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>
  if (!server) return <div className="text-center py-16 text-gray-400">Server 未找到</div>

  const handleInstall = async () => {
    try {
      const r = await installServer(server.id)
      setMessage(r.message || r.data?.detail || '安装完成')
      if (r.success) {
        setServer({ ...server, status: 'stopped' })
        const existing = JSON.parse(localStorage.getItem('mcp_hub_my_servers') || '[]')
        if (!existing.find((x: any) => x.name === server.id)) {
          existing.push({ name: server.id, command: (server as any).install_command || '', matched: true, hub_id: server.id })
          localStorage.setItem('mcp_hub_my_servers', JSON.stringify(existing))
        }
        if (r.data?.configs) {
          const agentCfg = r.data.configs.find((c: any) =>
            c.agent === AGENTS.find(a => a.id === selectedAgent)?.name
          )
          setConfigData(agentCfg || r.data.configs[0])
          setShowConfig(true)
        }
      }
    } catch (e: any) {
      setMessage(`安装失败: ${e.message || '未知错误'}`)
    }
  }

  const handleStart = async () => {
    try {
      const r = await startServer(server.id)
      setMessage(r.message || '已启动')
      if (r.success) setServer({ ...server, status: 'running' })
    } catch (e: any) {
      setMessage(`启动失败: ${e.message || '未知错误'}`)
    }
  }

  const handleStop = async () => {
    try {
      const r = await stopServer(server.id)
      setMessage(r.message || '已停止')
      if (r.success) setServer({ ...server, status: 'stopped' })
    } catch (e: any) {
      setMessage(`停止失败: ${e.message || '未知错误'}`)
    }
  }

  const handleUninstall = async () => {
    if (!window.confirm('确定要卸载吗？')) return
    try {
      const r = await apiPost<any>(`/servers/${encodeURIComponent(server.id)}/uninstall`)
      setMessage(r.message || '已卸载')
      if (r.success) {
        setServer({ ...server, status: 'not_installed' })
        setShowConfig(false)
      }
    } catch { setMessage('卸载失败') }
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
      // 同步 localStorage
      const favs = JSON.parse(localStorage.getItem('mcp_hub_favorites') || '[]')
      if (favd) { if (!favs.includes(server.id)) favs.push(server.id) }
      else { const idx = favs.indexOf(server.id); if (idx >= 0) favs.splice(idx, 1) }
      localStorage.setItem('mcp_hub_favorites', JSON.stringify(favs))
      // 触发其他 tab 更新
      window.dispatchEvent(new Event('storage'))
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
          {server.status === 'not_installed' && !isTracked && (
            <button onClick={handleInstall} className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors">
              📥 一键安装
            </button>
          )}
          {server.status === 'not_installed' && isTracked && (
            <button onClick={handleInstall} className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium transition-colors">
              📥 安装到本地
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
          <button onClick={handleFavorite} className={`px-4 py-2 border rounded-lg transition-colors ${isFavorited ? 'bg-yellow-50 border-yellow-300 text-yellow-700' : 'border-gray-300 hover:bg-gray-50'}`}>
            {isFavorited ? '⭐ 已收藏' : '☆ 收藏'}
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
                {(() => { const u = (reliability.uptime_stats as any[])?.find((u: any) => u.window === '24h'); return u ? (u.uptime_pct != null ? u.uptime_pct.toFixed(1) : '-') : '-'; })()}%
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
                    document.getElementById('review-input')?.focus()
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
          <textarea id="review-input" value={reviewText} onChange={e => setReviewText(e.target.value)}
            placeholder="分享你的使用体验..."
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none resize-none" />
          <button onClick={handleSubmitReview} disabled={submittingReview || !reviewText.trim()}
            className="mt-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 disabled:opacity-50 transition-colors">
            {submittingReview ? '提交中...' : replyTo ? '提交回复' : '提交评价'}
          </button>
        </div>
      </div>

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

    </div>
  )
}
