const API_BASE = '/api/v1'

export interface ServerInfo {
  id: string
  name: string
  display_name: string
  icon_url?: string
  description: string
  author: string
  categories: string[]
  tags: string[]
  rating: number
  review_count: number
  download_count: number
  status: string
  version: string
  homepage: string
  license: string
  security_level: string
}

export async function apiGet<T>(path: string): Promise<{ success: boolean; data: T; meta?: any }> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'x-user-id': getUserId() },
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

function getUserId(): string {
  try { return localStorage.getItem('mcp_hub_user') || 'anonymous' } catch { return 'anonymous' }
}

export async function apiPost<T>(path: string, body?: any): Promise<{ success: boolean; data?: T; message?: string }> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'x-user-id': getUserId() },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`API error: ${res.status}`)
  return res.json()
}

export async function searchServers(params: {
  q?: string
  category?: string
  sort?: string
  page?: number
}): Promise<{ data: ServerInfo[]; meta: { total: number } }> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.category) qs.set('category', params.category)
  if (params.sort) qs.set('sort', params.sort)
  if (params.page) qs.set('page', String(params.page))
  qs.set('page_size', '9')
  const res = await apiGet<ServerInfo[]>(`/market/search?${qs}`)
  return { data: res.data, meta: res.meta || { total: res.data.length } }
}

export async function getServer(id: string): Promise<ServerInfo> {
  const res = await apiGet<ServerInfo>(`/market/servers/${encodeURIComponent(id)}`)
  return res.data
}

export async function getTrending(): Promise<ServerInfo[]> {
  const res = await apiGet<ServerInfo[]>('/market/trending')
  return res.data
}

export async function getTopRated(): Promise<ServerInfo[]> {
  const res = await apiGet<ServerInfo[]>('/market/top-rated')
  return res.data
}

export async function healthCheck(): Promise<any> {
  return apiGet('/health')
}

export async function installServer(serverId: string): Promise<any> {
  return apiPost('/servers/install', { server_id: serverId })
}

export async function startServer(serverId: string): Promise<any> {
  return apiPost(`/servers/${encodeURIComponent(serverId)}/start`)
}

export async function stopServer(serverId: string): Promise<any> {
  return apiPost(`/servers/${encodeURIComponent(serverId)}/stop`)
}

export async function rateServer(serverId: string, rating: number, content?: string): Promise<any> {
  return apiPost('/community/rate', { server_id: serverId, rating, content: content || '' })
}

export async function favoriteServer(serverId: string): Promise<any> {
  return apiPost('/community/favorite', { server_id: serverId })
}

// === Auth ===

export interface AuthState {
  token: string | null
  userId: string | null
}

export function getAuthState(): AuthState {
  const token = localStorage.getItem('mcp_hub_token')
  const userId = localStorage.getItem('mcp_hub_user')
  return { token, userId }
}

export function setAuth(token: string, userId: string) {
  localStorage.setItem('mcp_hub_token', token)
  localStorage.setItem('mcp_hub_user', userId)
}

export function clearAuth() {
  localStorage.removeItem('mcp_hub_token')
  localStorage.removeItem('mcp_hub_user')
}

export function getLoginUrl(): string {
  return '/api/v1/auth/login'
}

export async function getMe(): Promise<any> {
  const { token } = getAuthState()
  if (!token) throw new Error('Not logged in')
  const res = await fetch(`${API_BASE}/auth/me`, {
    headers: { 'Authorization': `Bearer ${token}` },
  })
  if (!res.ok) throw new Error('Auth failed')
  return res.json()
}

// === SSE / Realtime ===

export function connectLogSSE(serverId: string, onLine: (line: string) => void): EventSource {
  const { token } = getAuthState()
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : ''
  const es = new EventSource(`${API_BASE}/realtime/logs/${encodeURIComponent(serverId)}${tokenParam}`)
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      if (d.line) onLine(d.line)
    } catch { /* ignore */ }
  }
  return es
}

export function connectStatusSSE(onStatus: (data: any) => void): EventSource {
  const { token } = getAuthState()
  const tokenParam = token ? `?token=${encodeURIComponent(token)}` : ''
  const es = new EventSource(`${API_BASE}/realtime/status${tokenParam}`)
  es.onmessage = (e) => {
    try {
      const d = JSON.parse(e.data)
      if (d.type === 'status') onStatus(d)
    } catch { /* ignore */ }
  }
  return es
}

export async function uploadConfig(file: File, agentId: string = ''): Promise<any> {
  const form = new FormData()
  form.append('file', file)
  const headers: Record<string, string> = { 'x-user-id': getUserId() }
  if (agentId) headers['x-agent-id'] = agentId
  const res = await fetch(`${API_BASE}/config/upload`, {
    method: 'POST',
    body: form,
    headers,
  })
  if (!res.ok) throw new Error(`Upload config failed: ${res.status}`)
  return res.json()
}

export async function downloadConfig(): Promise<Blob> {
  const res = await fetch(`${API_BASE}/config/download`, {
    headers: { 'x-user-id': getUserId() },
  })
  if (!res.ok) throw new Error(`Download config failed: ${res.status}`)
  return res.blob()
}

export async function exportConfig(share: boolean): Promise<Blob> {
  const res = await fetch(`${API_BASE}/export/config?share=${share}`, {
    headers: { 'x-user-id': getUserId() },
  })
  if (!res.ok) throw new Error(`Export config failed: ${res.status}`)
  return res.blob()
}

export async function searchAdvanced(params: {
  q?: string; category?: string; tag?: string; author?: string; language?: string; install_type?: string; security_level?: string; tracked_filter?: string; sort?: string; page?: number; page_size?: number
}): Promise<{ success: boolean; data: ServerInfo[]; meta: { total: number; page: number; page_size: number } }> {
  const qs = new URLSearchParams()
  if (params.q) qs.set('q', params.q)
  if (params.category) qs.set('category', params.category)
  if (params.tag) qs.set('tag', params.tag)
  if (params.author) qs.set('author', params.author)
  if (params.language) qs.set('language', params.language)
  if (params.install_type) qs.set('install_type', params.install_type)
  if (params.security_level) qs.set('security_level', params.security_level)
  if (params.sort) qs.set('sort', params.sort)
  if (params.page) qs.set('page', String(params.page))
  qs.set('page_size', '9')
  const res = await fetch(`${API_BASE}/search/advanced?${qs}`, {
    headers: { 'x-user-id': getUserId() },
  })
  if (!res.ok) throw new Error(`Search failed: ${res.status}`)
  return res.json()
}

// === Security Scanning ===

export interface SecurityScanResult {
  server_id: string
  score: number
  level: string
  network_access: boolean
  file_access: boolean
  findings: Array<{ severity: string; title: string; description: string; score_impact: number }>
}

export async function scanServerSecurity(serverId: string): Promise<{ success: boolean; data: SecurityScanResult }> {
  return apiGet(`/security/scan/${encodeURIComponent(serverId)}`)
}

// === Token Analysis ===

export interface TokenAnalysisResult {
  server_id: string
  total_tokens: number
  context_pct: number
  tool_count: number
  estimated: boolean
  suggestions: string[]
}

export async function analyzeServerTokens(serverId: string): Promise<{ success: boolean; data: TokenAnalysisResult }> {
  return apiGet(`/tokens/analyze/${encodeURIComponent(serverId)}`)
}

// === Monitoring ===

export interface UptimeStats {
  window: string
  total_checks: number
  passed_checks: number
  uptime_pct: number
  avg_response_time_ms: number
}

export interface ReliabilityResult {
  server_id: string
  reliability_score: number
  total_checks: number
  last_check_at: string | null
  uptime_stats: UptimeStats[]
}

export interface MonitorSummary {
  total_servers: number
  running: number
  total_health_checks: number
  errors_last_24h: number
}

export async function getServerUptime(serverId: string): Promise<{ success: boolean; data: UptimeStats[] }> {
  return apiGet(`/health/uptime/${encodeURIComponent(serverId)}`)
}

export async function getServerReliability(serverId: string): Promise<{ success: boolean; data: ReliabilityResult }> {
  return apiGet(`/health/reliability/${encodeURIComponent(serverId)}`)
}

export async function getTopReliable(limit?: number): Promise<{ success: boolean; data: ReliabilityResult[] }> {
  return apiGet(`/health/reliability/top${limit ? `?limit=${limit}` : ''}`)
}

export async function getMonitorSummary(): Promise<{ success: boolean; data: MonitorSummary }> {
  return apiGet('/health/summary')
}
