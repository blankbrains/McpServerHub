import { Link } from 'react-router-dom'
import type { ServerInfo } from '../api/client'
import StatusBadge from './StatusBadge'

interface ServerCardProps {
  server: ServerInfo
  showInstall?: boolean
}

export default function ServerCard({ server }: ServerCardProps) {
  const stars = '⭐'.repeat(Math.round(server.rating)) + '☆'.repeat(5 - Math.round(server.rating))
  const securityLabels: Record<string, string> = {
    verified: '🔒 安全认证',
    reviewed: '⚪ 已审查',
    unreviewed: '⚠️ 未审查',
  }
  const name = server.display_name || server.name || server.id.split('/').pop() || '?'

  return (
    <Link
      to={`/servers/${encodeURIComponent(server.id)}`}
      className="block bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-blue-200 transition-all"
    >
      <div className="flex items-start gap-3 mb-2">
        {/* Icon */}
        {server.icon_url ? (
          <img src={server.icon_url} alt="" className="w-10 h-10 rounded-lg flex-shrink-0" />
        ) : (
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center flex-shrink-0 text-white font-bold text-lg">
            {name[0].toUpperCase()}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-gray-900 text-sm truncate">{server.id}</h3>
            <StatusBadge status={server.status} />
          </div>
          <p className="text-xs text-gray-400 mt-0.5">{name}</p>
        </div>
      </div>

      <p className="text-sm text-gray-600 line-clamp-2 mb-3">
        {server.description || '暂无描述'}
      </p>

      <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
        <span>{stars}</span>
        <span>📥 {server.download_count}</span>
        <span>💬 {server.review_count}</span>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {server.categories?.slice(0, 2).map((cat) => (
          <span key={cat} className="px-2 py-0.5 bg-blue-50 text-blue-600 rounded text-xs">
            {cat}
          </span>
        ))}
        <span className="text-xs text-gray-400">
          {securityLabels[server.security_level] || server.security_level}
        </span>
      </div>
    </Link>
  )
}
