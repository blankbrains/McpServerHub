import { Link } from 'react-router-dom'
import type { ServerInfo } from '../api/client'
import StatusBadge from './StatusBadge'

interface ServerCardProps {
  server: ServerInfo
  showInstall?: boolean
}

export default function ServerCard({ server, showInstall }: ServerCardProps) {
  const stars = '⭐'.repeat(Math.round(server.rating)) + '☆'.repeat(5 - Math.round(server.rating))
  const securityLabels: Record<string, string> = {
    verified: '🔒 安全认证',
    reviewed: '⚪ 已审查',
    unreviewed: '⚠️ 未审查',
  }

  return (
    <Link
      to={`/servers/${encodeURIComponent(server.id)}`}
      className="block bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md hover:border-blue-200 transition-all"
    >
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="font-semibold text-gray-900 text-base">{server.id}</h3>
          <p className="text-xs text-gray-400 mt-0.5">v{server.version || '?'}</p>
        </div>
        <StatusBadge status={server.status} />
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
