interface StatusBadgeProps {
  status: string
}

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config: Record<string, { color: string; icon: string; label: string }> = {
    running: { color: 'bg-green-100 text-green-800', icon: '🟢', label: '运行中' },
    stopped: { color: 'bg-gray-100 text-gray-600', icon: '⏹', label: '已停止' },
    error: { color: 'bg-red-100 text-red-800', icon: '🔴', label: '异常' },
    not_installed: { color: 'bg-gray-50 text-gray-400', icon: '📥', label: '未安装' },
  }
  const c = config[status] || { color: 'bg-gray-100 text-gray-600', icon: '❓', label: status }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${c.color}`}>
      {c.icon} {c.label}
    </span>
  )
}
