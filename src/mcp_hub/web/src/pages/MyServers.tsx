import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { apiGet, ServerInfo } from '../api/client'
import ServerCard from '../components/ServerCard'

export default function MyServers() {
  const [servers, setServers] = useState<ServerInfo[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiGet<ServerInfo[]>('/servers/')
      .then((res) => setServers(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-16 text-gray-400">加载中...</div>

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900">📦 我的 Server</h1>
      <p className="text-gray-500">你已安装的 MCP Server</p>

      {servers.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl border border-gray-200">
          <div className="text-4xl mb-4">📭</div>
          <p className="text-gray-500 mb-2">还没有安装任何 Server</p>
          <Link to="/market" className="text-blue-600 hover:text-blue-800">去市场看看 →</Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {servers.map((s) => (
            <ServerCard key={s.id} server={s} />
          ))}
        </div>
      )}
    </div>
  )
}
