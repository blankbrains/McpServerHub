const API_BASE = '/api/v1'
const AUTH_TOKEN_KEY = 'mcp_hub_token'
const AUTH_USER_KEY = 'mcp_hub_user'

export const AUTH_STATE_EVENT = 'mcp-hub-auth-state'

export class ApiRequestError extends Error {
  constructor(public readonly status: number, message?: string) {
    super(message || `API error: ${status}`)
    this.name = 'ApiRequestError'
  }
}

export interface AuthState {
  token: string | null
  userId: string | null
}

let cachedAuthState: AuthState = { token: null, userId: null }

function readAuthState(): AuthState {
  if (typeof window === 'undefined') return cachedAuthState
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  const userId = token ? localStorage.getItem(AUTH_USER_KEY) : null
  if (cachedAuthState.token !== token || cachedAuthState.userId !== userId) {
    cachedAuthState = { token, userId }
  }
  return cachedAuthState
}

function publishAuthState(): void {
  window.dispatchEvent(new Event(AUTH_STATE_EVENT))
}

export function subscribeAuthState(listener: () => void): () => void {
  const handleAuthState = () => listener()
  const handleStorage = (event: StorageEvent) => {
    if (event.key === AUTH_TOKEN_KEY || event.key === AUTH_USER_KEY || event.key === null) {
      listener()
    }
  }
  window.addEventListener(AUTH_STATE_EVENT, handleAuthState)
  window.addEventListener('storage', handleStorage)
  return () => {
    window.removeEventListener(AUTH_STATE_EVENT, handleAuthState)
    window.removeEventListener('storage', handleStorage)
  }
}

export function getAuthHeaders(): Record<string, string> {
  const token = readAuthState().token
  if (token) {
    return { 'Authorization': `Bearer ${token}` }
  }
  return {}
}

export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const tokenUsed = readAuthState().token
  const headers = new Headers(init.headers)
  if (tokenUsed && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${tokenUsed}`)
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (
    response.status === 401
    && tokenUsed
    && localStorage.getItem(AUTH_TOKEN_KEY) === tokenUsed
  ) {
    clearAuth()
  }
  return response
}

export async function readApiErrorMessage(
  response: Response,
  fallback: string,
): Promise<string> {
  try {
    const payload = await response.json()
    const nestedMessage = payload?.error?.message
    if (typeof nestedMessage === 'string' && nestedMessage.trim()) {
      return nestedMessage.trim()
    }
    if (typeof payload?.detail === 'string' && payload.detail.trim()) {
      return payload.detail.trim()
    }
    if (typeof payload?.message === 'string' && payload.message.trim()) {
      return payload.message.trim()
    }
  } catch {
    // Non-JSON errors use the caller's stable fallback.
  }
  return fallback
}

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
  catalog_source?: string
  catalog_source_id?: string
  catalog_status?: string
  runtime_config_available?: boolean
  config_template?: Record<string, string>
  registry?: {
    source: string
    upstream_id: string
    version: string
    package_type: string
    package_identifier: string
    repository_url: string
    transport: string
    status: string
    published_at: string
    updated_at: string
    last_synced_at: string
  }
}

export async function apiGet<T>(path: string): Promise<{ success: boolean; data: T; meta?: any }> {
  const res = await apiFetch(path)
  if (!res.ok) throw new ApiRequestError(res.status)
  return res.json()
}

export async function apiPost<T>(path: string, body?: any): Promise<{ success: boolean; data?: T; message?: string }> {
  const res = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiRequestError(res.status)
  return res.json()
}

export async function apiDelete<T>(path: string): Promise<{ success: boolean; data?: T; message?: string }> {
  const res = await apiFetch(path, {
    method: 'DELETE',
  })
  if (!res.ok) throw new ApiRequestError(res.status)
  return res.json()
}

export async function apiPatch<T>(path: string, body?: any): Promise<{ success: boolean; data?: T; message?: string }> {
  const res = await apiFetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiRequestError(res.status)
  return res.json()
}

export async function apiPut<T>(path: string, body?: any): Promise<{ success: boolean; data?: T; message?: string }> {
  const res = await apiFetch(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new ApiRequestError(res.status)
  return res.json()
}

export async function apiDownload(path: string, fallbackFilename: string): Promise<void> {
  const res = await apiFetch(path)
  if (!res.ok) throw new ApiRequestError(res.status)
  const disposition = res.headers.get('Content-Disposition') || ''
  const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1]
  const plainName = disposition.match(/filename="?([^";]+)"?/i)?.[1]
  const filename = encodedName
    ? decodeURIComponent(encodedName)
    : plainName || fallbackFilename
  const url = URL.createObjectURL(await res.blob())
  try {
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
  } finally {
    URL.revokeObjectURL(url)
  }
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

export async function getFavoriteServers(): Promise<{ success: boolean; data: ServerInfo[] }> {
  return apiGet<ServerInfo[]>('/community/favorites')
}

export function getAuthState(): AuthState {
  return readAuthState()
}

export function setAuth(token: string, userId: string) {
  localStorage.setItem(AUTH_TOKEN_KEY, token)
  localStorage.setItem(AUTH_USER_KEY, userId)
  readAuthState()
  publishAuthState()
}

export function clearAuth() {
  const hadAuth = Boolean(
    localStorage.getItem(AUTH_TOKEN_KEY) || localStorage.getItem(AUTH_USER_KEY)
  )
  localStorage.removeItem(AUTH_TOKEN_KEY)
  localStorage.removeItem(AUTH_USER_KEY)
  readAuthState()
  if (hadAuth) publishAuthState()
}

export function getLoginUrl(): string {
  return '/api/v1/auth/login'
}

export async function getMe(): Promise<any> {
  if (!getAuthState().token) throw new Error('Not logged in')
  return apiGet('/auth/me')
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

export async function uploadConfig(
  file: File,
  agentId: string = '',
  trackServers: boolean = false,
): Promise<any> {
  const form = new FormData()
  form.append('file', file)
  const headers: Record<string, string> = {}
  if (agentId) headers['x-agent-id'] = agentId
  headers['x-track-servers'] = String(trackServers)
  const res = await apiFetch('/config/upload', {
    method: 'POST',
    body: form,
    headers,
  })
  if (!res.ok) throw new ApiRequestError(res.status, `Upload config failed: ${res.status}`)
  return res.json()
}

export async function downloadConfig(): Promise<Blob> {
  const res = await apiFetch('/config/download')
  if (!res.ok) throw new ApiRequestError(res.status, `Download config failed: ${res.status}`)
  return res.blob()
}

export async function exportConfig(share: boolean): Promise<Blob> {
  const res = await apiFetch(`/export/config?share=${share}`)
  if (!res.ok) throw new ApiRequestError(res.status, `Export config failed: ${res.status}`)
  return res.blob()
}

export async function exportTelemetryReport(days: number = 7): Promise<Blob> {
  const res = await apiFetch(`/export/telemetry-report?days=${days}`)
  if (!res.ok) {
    throw new ApiRequestError(res.status, `Telemetry report export failed: ${res.status}`)
  }
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
  if (params.tracked_filter) qs.set('tracked_filter', params.tracked_filter)
  if (params.sort) qs.set('sort', params.sort)
  if (params.page) qs.set('page', String(params.page))
  qs.set('page_size', '9')
  const res = await apiFetch(`/search/advanced?${qs}`)
  if (!res.ok) throw new ApiRequestError(res.status, `Search failed: ${res.status}`)
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
