export const NOTIFICATION_COUNT_EVENT = 'mcp-hub:notification-count'

export function publishNotificationCount(count: number): void {
  window.dispatchEvent(new CustomEvent(NOTIFICATION_COUNT_EVENT, {
    detail: { count: Math.max(0, count) },
  }))
}
