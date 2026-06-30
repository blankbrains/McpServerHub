/** 离线缓存服务 — 当 Hub API 不可达时从 localStorage 提供降级数据。 */

const CACHE_PREFIX = 'mcp_hub_cache_'
const CACHE_TTL_MS: Record<string, number> = {
  market_servers: 30 * 60 * 1000,  // 30 分钟
  market_categories: 60 * 60 * 1000,  // 1 小时
  trending: 10 * 60 * 1000,  // 10 分钟
  config: 60 * 60 * 1000,  // 1 小时
  health: 5 * 60 * 1000,  // 5 分钟
  default: 30 * 60 * 1000,
}

interface CacheEntry<T> {
  data: T
  timestamp: number
  ttl: number
}

export const OfflineCache = {
  set<T>(key: string, data: T, category?: string): void {
    try {
      const ttl = CACHE_TTL_MS[category || 'default'] || CACHE_TTL_MS.default
      const entry: CacheEntry<T> = { data, timestamp: Date.now(), ttl }
      localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry))
    } catch { /* quota exceeded or disabled */ }
  },

  get<T>(key: string): T | null {
    try {
      const raw = localStorage.getItem(CACHE_PREFIX + key)
      if (!raw) return null
      const entry: CacheEntry<T> = JSON.parse(raw)
      if (Date.now() - entry.timestamp > entry.ttl) {
        localStorage.removeItem(CACHE_PREFIX + key)
        return null
      }
      return entry.data
    } catch { return null }
  },

  remove(key: string): void {
    localStorage.removeItem(CACHE_PREFIX + key)
  },

  keys(): string[] {
    const result: string[] = []
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i)
      if (key?.startsWith(CACHE_PREFIX)) {
        result.push(key.slice(CACHE_PREFIX.length))
      }
    }
    return result
  },

  /** 检查缓存是否仍然新鲜 */
  isFresh(key: string): boolean {
    return this.get(key) !== null
  },
}

/** 判断当前是否离线 */
export function isOnline(): boolean {
  return typeof navigator !== 'undefined' ? navigator.onLine : true
}

/** 离线感知的 fetch 包装器 */
export async function offlineAwareFetch<T>(
  cacheKey: string,
  fetchFn: () => Promise<T>,
  category?: string,
): Promise<{ data: T; fromCache: boolean }> {
  if (!isOnline()) {
    const cached = OfflineCache.get<T>(cacheKey)
    if (cached) return { data: cached, fromCache: true }
    throw new Error('离线状态且无缓存数据')
  }

  try {
    const data = await fetchFn()
    OfflineCache.set(cacheKey, data, category)
    return { data, fromCache: false }
  } catch {
    const cached = OfflineCache.get<T>(cacheKey)
    if (cached) return { data: cached, fromCache: true }
    throw new Error('网络请求失败且无缓存数据')
  }
}
