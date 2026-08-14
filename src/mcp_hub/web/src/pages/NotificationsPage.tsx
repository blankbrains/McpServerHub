import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  apiDelete,
  apiGet,
  apiPatch,
  apiPost,
} from '../api/client'
import AuthRequired from '../components/AuthRequired'
import { useAuthState } from '../hooks/useAuthState'
import { publishNotificationCount } from '../utils/notifications'

type AlertStatus = 'all' | 'active' | 'resolved' | 'suppressed'

interface NotifItem {
  id: number
  type: string
  title: string
  message: string
  server_id: string
  link: string
  is_read: boolean
  alert_rule: string
  severity: 'high' | 'warning' | string
  status: Exclude<AlertStatus, 'all'> | string
  occurrence_count: number
  first_seen_at: string
  last_seen_at: string
  resolved_at: string
  observed_value: string
  created_at: string
}

interface AlertRule {
  rule: string
  label: string
  description: string
  enabled: boolean
  threshold: number
  default_threshold: number
  minimum_threshold: number
  maximum_threshold: number
  unit: string
  severity: 'high' | 'warning'
}

interface NotificationResponse {
  items: NotifItem[]
  unread_count: number
}

const statusOptions: Array<{ value: AlertStatus; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '处理中' },
  { value: 'resolved', label: '已恢复' },
  { value: 'suppressed', label: '已暂停' },
]

const typeLabels: Record<string, string> = {
  alert: '告警',
  update: '更新',
  reply: '回复',
  system: '系统',
}

function formatDate(value: string): string {
  if (!value) return '未记录'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value.slice(0, 16)
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(parsed)
}

function statusClass(status: string): string {
  if (status === 'active') return 'border-rose-200 bg-rose-50 text-rose-800 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200'
  if (status === 'resolved') return 'border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-900/70 dark:bg-emerald-950/40 dark:text-emerald-200'
  if (status === 'suppressed') return 'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900/70 dark:bg-amber-950/40 dark:text-amber-200'
  return 'border-gray-200 bg-gray-50 text-gray-700 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300'
}

function statusLabel(status: string): string {
  if (status === 'active') return '处理中'
  if (status === 'resolved') return '已恢复'
  if (status === 'suppressed') return '已暂停'
  return typeLabels[status] || status
}

export default function NotificationsPage() {
  const auth = useAuthState()
  const [items, setItems] = useState<NotifItem[]>([])
  const [rules, setRules] = useState<AlertRule[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [status, setStatus] = useState<AlertStatus>('active')
  const [loading, setLoading] = useState(true)
  const [settingsLoading, setSettingsLoading] = useState(true)
  const [error, setError] = useState('')
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set())
  const [savingRules, setSavingRules] = useState<Set<string>>(new Set())
  const { token } = auth

  const loadNotifications = async (nextStatus = status) => {
    if (!token) {
      setItems([])
      setUnreadCount(0)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const response = await apiGet<NotificationResponse>(
        `/notifications?page_size=50&status=${nextStatus}&unread_only=${nextStatus === 'active'}`,
      )
      setItems(response.data.items)
      setUnreadCount(response.data.unread_count)
      publishNotificationCount(response.data.unread_count)
    } catch {
      setError('加载通知失败，请检查网络后重试。')
    } finally {
      setLoading(false)
    }
  }

  const loadSettings = async () => {
    if (!token) {
      setRules([])
      setSettingsLoading(false)
      return
    }
    setSettingsLoading(true)
    try {
      const response = await apiGet<{ rules: AlertRule[] }>('/notifications/settings')
      setRules(response.data.rules)
    } catch {
      setError('加载告警设置失败，请稍后重试。')
    } finally {
      setSettingsLoading(false)
    }
  }

  const load = async (nextStatus = status) => {
    setError('')
    await Promise.all([loadNotifications(nextStatus), loadSettings()])
  }

  useEffect(() => {
    void load()
  }, [token])

  const selectStatus = (nextStatus: AlertStatus) => {
    setStatus(nextStatus)
    void loadNotifications(nextStatus)
  }

  const markRead = async (notification: NotifItem) => {
    if (notification.is_read) return
    const previousItems = items
    const previousCount = unreadCount
    const nextCount = notification.status === 'active'
      ? Math.max(0, previousCount - 1)
      : previousCount
    setItems(previous => previous.map(item => (
      item.id === notification.id ? { ...item, is_read: true } : item
    )))
    setUnreadCount(nextCount)
    publishNotificationCount(nextCount)
    try {
      await apiPost(`/notifications/${notification.id}/read`)
      if (status === 'active') {
        setItems(previous => previous.filter(item => item.id !== notification.id))
      }
    } catch {
      setItems(previousItems)
      setUnreadCount(previousCount)
      publishNotificationCount(previousCount)
      setError('标记已读失败。')
    }
  }

  const markAllRead = async () => {
    const previousItems = items
    const previousCount = unreadCount
    setItems(previous => previous.map(item => ({ ...item, is_read: true })))
    setUnreadCount(0)
    publishNotificationCount(0)
    try {
      await apiPost('/notifications/read-all')
      if (status === 'active') setItems([])
    } catch {
      setItems(previousItems)
      setUnreadCount(previousCount)
      publishNotificationCount(previousCount)
      setError('标记已读失败。')
    }
  }

  const deleteNotification = async (
    notification: NotifItem,
    event: React.MouseEvent<HTMLButtonElement>,
  ) => {
    event.stopPropagation()
    const actionLabel = notification.type === 'alert' && notification.status === 'active'
      ? '忽略告警'
      : '删除通知'
    if (!window.confirm(`确定${actionLabel}“${notification.title}”？`)) return
    setDeletingIds(previous => new Set(previous).add(notification.id))
    setError('')
    const previousItems = items
    const previousCount = unreadCount
    try {
      await apiDelete(`/notifications/${notification.id}`)
      setItems(previous => previous.filter(item => item.id !== notification.id))
      if (!notification.is_read && notification.status === 'active') {
        const nextCount = Math.max(0, previousCount - 1)
        setUnreadCount(nextCount)
        publishNotificationCount(nextCount)
      }
    } catch {
      setItems(previousItems)
      setUnreadCount(previousCount)
      publishNotificationCount(previousCount)
      setError('删除通知失败，请稍后重试。')
    } finally {
      setDeletingIds(previous => {
        const next = new Set(previous)
        next.delete(notification.id)
        return next
      })
    }
  }

  const updateRule = async (rule: AlertRule, changes: Partial<Pick<AlertRule, 'enabled' | 'threshold'>>) => {
    const nextRule = { ...rule, ...changes }
    if (
      nextRule.threshold < nextRule.minimum_threshold
      || nextRule.threshold > nextRule.maximum_threshold
    ) {
      setError(`${rule.label} 的阈值范围为 ${rule.minimum_threshold}-${rule.maximum_threshold}${rule.unit}。`)
      return
    }

    const previousRules = rules
    setRules(previous => previous.map(item => (
      item.rule === rule.rule ? nextRule : item
    )))
    setSavingRules(previous => new Set(previous).add(rule.rule))
    setError('')
    try {
      await apiPatch(`/notifications/settings/${encodeURIComponent(rule.rule)}`, {
        enabled: nextRule.enabled,
        threshold: nextRule.threshold,
      })
      await loadNotifications(status)
    } catch {
      setRules(previousRules)
      setError(`保存“${rule.label}”失败。`)
    } finally {
      setSavingRules(previous => {
        const next = new Set(previous)
        next.delete(rule.rule)
        return next
      })
    }
  }

  if (!token) {
    return (
      <AuthRequired
        title="登录后查看告警和通知"
        description="设备、Gateway 和本地 MCP 告警按账户隔离，登录后才能查看、处理和调整规则。"
      />
    )
  }

  return (
    <div className="mx-auto max-w-5xl">
      <header className="border-b border-gray-200 pb-5 dark:border-gray-700">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500 dark:text-gray-400">Operations</p>
            <h1 className="mt-1 text-2xl font-semibold text-gray-950 dark:text-white">通知中心</h1>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
              默认仅显示尚未处理的活动告警。
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              当前筛选 {items.length} 项，{unreadCount} 项未读
            </span>
            {unreadCount > 0 && (
              <button
                type="button"
                onClick={() => void markAllRead()}
                className="border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:border-gray-500 hover:text-gray-950 dark:border-gray-600 dark:text-gray-200 dark:hover:border-gray-400 dark:hover:text-white"
              >
                全部标为已读
              </button>
            )}
          </div>
        </div>
      </header>

      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-b border-gray-200 pb-3 dark:border-gray-700">
        <div className="flex rounded-md border border-gray-300 p-0.5 dark:border-gray-600" role="tablist" aria-label="通知状态筛选">
          {statusOptions.map(option => (
            <button
              key={option.value}
              type="button"
              role="tab"
              aria-selected={status === option.value}
              onClick={() => selectStatus(option.value)}
              className={`px-3 py-1.5 text-sm transition-colors ${
                status === option.value
                  ? 'bg-gray-900 text-white dark:bg-white dark:text-gray-950'
                  : 'text-gray-600 hover:text-gray-950 dark:text-gray-400 dark:hover:text-white'
              }`}
            >
              {option.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => void load()}
          className="text-sm text-gray-500 underline-offset-4 hover:text-gray-950 hover:underline dark:text-gray-400 dark:hover:text-white"
        >
          刷新
        </button>
      </div>

      {error && (
        <div className="mt-4 flex items-center justify-between gap-3 border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800 dark:border-rose-900/70 dark:bg-rose-950/40 dark:text-rose-200" role="alert">
          <span>{error}</span>
          <button type="button" onClick={() => void load()} className="font-medium underline underline-offset-4">重试</button>
        </div>
      )}

      <section className="mt-4" aria-label="通知列表">
        {loading ? (
          <div className="space-y-3" aria-label="正在加载通知">
            {[0, 1, 2].map(index => (
              <div key={index} className="h-28 animate-pulse border border-gray-200 bg-gray-100 dark:border-gray-700 dark:bg-gray-800" />
            ))}
          </div>
        ) : items.length === 0 ? (
          <div className="border-y border-gray-200 py-12 text-center dark:border-gray-700">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-200">当前筛选条件下没有通知</p>
            <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">已接入 Gateway 后，异常、恢复和配置冲突会显示在这里。</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 border-y border-gray-200 dark:divide-gray-700 dark:border-gray-700">
            {items.map(notification => (
              <article
                key={notification.id}
                className={`grid gap-3 px-1 py-4 sm:grid-cols-[auto_minmax(0,1fr)_auto] sm:px-3 ${notification.is_read ? 'opacity-70' : ''}`}
                onClick={() => void markRead(notification)}
              >
                <div className="flex items-start gap-2 pt-0.5">
                  <span className={`inline-flex border px-2 py-1 text-xs font-medium ${statusClass(notification.status)}`}>
                    {notification.type === 'alert' ? statusLabel(notification.status) : typeLabels[notification.type] || notification.type}
                  </span>
                  {notification.type === 'alert' && (
                    <span className={`inline-flex border px-2 py-1 text-xs font-medium ${
                      notification.severity === 'high'
                        ? 'border-rose-200 text-rose-700 dark:border-rose-900 dark:text-rose-300'
                        : 'border-amber-200 text-amber-700 dark:border-amber-900 dark:text-amber-300'
                    }`}>
                      {notification.severity === 'high' ? '高优先级' : '注意'}
                    </span>
                  )}
                </div>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <h2 className="text-sm font-semibold text-gray-950 dark:text-white">{notification.title}</h2>
                    {!notification.is_read && notification.status === 'active' && (
                      <span className="h-1.5 w-1.5 rounded-full bg-rose-500" aria-label="未读" />
                    )}
                  </div>
                  {notification.message && <p className="mt-1 text-sm leading-6 text-gray-600 dark:text-gray-300">{notification.message}</p>}
                  <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-500 dark:text-gray-400">
                    {notification.observed_value && <div><dt className="sr-only">观测值</dt><dd>观测值：{notification.observed_value}</dd></div>}
                    {notification.type === 'alert' && <div><dt className="sr-only">发生次数</dt><dd>事件次数：{notification.occurrence_count}</dd></div>}
                    <div><dt className="sr-only">最后更新</dt><dd>最后更新：{formatDate(notification.last_seen_at || notification.created_at)}</dd></div>
                    {notification.status === 'resolved' && <div><dt className="sr-only">恢复时间</dt><dd>恢复：{formatDate(notification.resolved_at)}</dd></div>}
                  </dl>
                </div>
                <div className="flex items-start justify-end gap-3">
                  {notification.link && (
                    <Link
                      to={notification.link}
                      onClick={event => {
                        event.stopPropagation()
                        void markRead(notification)
                      }}
                      className="text-sm font-medium text-gray-700 underline-offset-4 hover:text-gray-950 hover:underline dark:text-gray-300 dark:hover:text-white"
                    >
                      查看
                    </Link>
                  )}
                  <button
                    type="button"
                    onClick={event => void deleteNotification(notification, event)}
                    disabled={deletingIds.has(notification.id)}
                    aria-label={`${notification.type === 'alert' && notification.status === 'active' ? '忽略' : '删除'}通知：${notification.title}`}
                    className="text-sm text-gray-400 underline-offset-4 hover:text-rose-700 hover:underline disabled:cursor-not-allowed disabled:opacity-50 dark:hover:text-rose-300"
                  >
                    {deletingIds.has(notification.id)
                      ? '处理中'
                      : notification.type === 'alert' && notification.status === 'active'
                      ? '忽略'
                      : '删除'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        )}
      </section>

      <section className="mt-10 border-t border-gray-200 pt-5 dark:border-gray-700" aria-labelledby="alert-settings-title">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-gray-500 dark:text-gray-400">Policy</p>
            <h2 id="alert-settings-title" className="mt-1 text-lg font-semibold text-gray-950 dark:text-white">告警规则</h2>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">暂停规则会关闭当前告警，不删除历史记录。</p>
        </div>

        {settingsLoading ? (
          <div className="mt-4 space-y-2" aria-label="正在加载告警规则">
            {[0, 1, 2].map(index => <div key={index} className="h-20 animate-pulse border border-gray-200 bg-gray-100 dark:border-gray-700 dark:bg-gray-800" />)}
          </div>
        ) : (
          <div className="mt-4 divide-y divide-gray-200 border-y border-gray-200 dark:divide-gray-700 dark:border-gray-700">
            {rules.map(rule => (
              <div key={rule.rule} className="grid gap-4 px-1 py-4 md:grid-cols-[minmax(0,1fr)_auto_auto] md:items-center md:px-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h3 className="text-sm font-semibold text-gray-900 dark:text-white">{rule.label}</h3>
                    <span className={`text-xs ${rule.severity === 'high' ? 'text-rose-700 dark:text-rose-300' : 'text-amber-700 dark:text-amber-300'}`}>
                      {rule.severity === 'high' ? '高优先级' : '注意'}
                    </span>
                  </div>
                  <p className="mt-1 text-sm leading-6 text-gray-500 dark:text-gray-400">{rule.description}</p>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-200">
                  <span>阈值</span>
                  <input
                    type="number"
                    value={rule.threshold}
                    min={rule.minimum_threshold}
                    max={rule.maximum_threshold}
                    step={Number.isInteger(rule.default_threshold) ? 1 : 0.1}
                    disabled={savingRules.has(rule.rule)}
                    onChange={event => setRules(previous => previous.map(item => (
                      item.rule === rule.rule ? { ...item, threshold: Number(event.target.value) } : item
                    )))}
                    onBlur={() => {
                      const current = rules.find(item => item.rule === rule.rule)
                      if (current && current.threshold !== rule.threshold) void updateRule(rule, { threshold: current.threshold })
                    }}
                    aria-label={`${rule.label}阈值`}
                    className="w-24 border border-gray-300 bg-white px-2 py-1.5 text-right text-sm text-gray-900 outline-none focus:border-gray-900 dark:border-gray-600 dark:bg-gray-800 dark:text-white dark:focus:border-white"
                  />
                  <span className="min-w-8 text-xs text-gray-500 dark:text-gray-400">{rule.unit}</span>
                </label>
                <button
                  type="button"
                  role="switch"
                  aria-checked={rule.enabled}
                  disabled={savingRules.has(rule.rule)}
                  onClick={() => void updateRule(rule, { enabled: !rule.enabled })}
                  className={`inline-flex min-w-20 justify-center border px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                    rule.enabled
                      ? 'border-gray-900 bg-gray-900 text-white dark:border-white dark:bg-white dark:text-gray-950'
                      : 'border-gray-300 text-gray-600 hover:border-gray-500 dark:border-gray-600 dark:text-gray-300'
                  }`}
                >
                  {savingRules.has(rule.rule) ? '保存中' : rule.enabled ? '已启用' : '已暂停'}
                </button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
