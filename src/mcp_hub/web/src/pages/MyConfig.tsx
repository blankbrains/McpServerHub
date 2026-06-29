import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

interface ConfigServer {
  name: string
  command: string
  hub_id?: string
  hub_install_command?: string
  matched?: boolean
}

export default function MyConfig() {
  const [servers, setServers] = useState<ConfigServer[]>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_my_servers') || '[]') }
    catch { return [] }
  })
  const [downloading, setDownloading] = useState(false)
  const [message, setMessage] = useState('')

  // Save to localStorage whenever servers change
  useEffect(() => {
    localStorage.setItem('mcp_hub_my_servers', JSON.stringify(servers))
  }, [servers])

  const removeServer = (name: string) => {
    setServers(prev => prev.filter(s => s.name !== name))
    setMessage(`已移除 ${name}`)
    setTimeout(() => setMessage(''), 3000)
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/v1/config/upload', { method: 'POST', body: form })
      const result = await res.json()
      if (result.success && result.data) {
        const { matched, unmatched } = result.data
        const newServers: ConfigServer[] = []
        for (const m of (matched || [])) {
          if (!servers.find(s => s.name === m.local_name)) {
            newServers.push({
              name: m.hub_id || m.local_name,
              command: m.hub_install_command || m.local_command,
              hub_id: m.hub_id,
              matched: true,
            })
          }
        }
        for (const u of (unmatched || [])) {
          if (!servers.find(s => s.name === u.local_name)) {
            newServers.push({
              name: u.local_name,
              command: u.local_command,
              matched: false,
            })
          }
        }
        if (newServers.length > 0) {
          setServers(prev => [...prev, ...newServers])
          setMessage(`已添加 ${newServers.length} 个 Server`)
        } else {
          setMessage('所有 Server 已在列表中')
        }
      } else {
        setMessage(result.error || '上传失败')
      }
    } catch {
      setMessage('上传失败')
    }
    setTimeout(() => setMessage(''), 3000)
  }

  const handleDownload = async () => {
    if (servers.length === 0) return
    setDownloading(true)
    try {
      // 从匹配的 Server 中提取 hub_id
      const hubIds = servers
        .filter(s => s.matched && s.hub_id)
        .map(s => s.hub_id as string)

      if (hubIds.length === 0) {
        // 没有匹配的 Server，生成基础配置
        const config: any = { mcpServers: {} }
        for (const s of servers) {
          if (s.command) {
            const parts = s.command.split(' ')
            config.mcpServers[s.name.split('/').pop() || s.name] = {
              command: parts[0],
              args: parts.slice(1),
            }
          }
        }
        config.mcpServers['mcp-hub-gateway'] = { command: 'mcp', args: ['serve'] }
        const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = 'mcp-hub-config.json'; a.click()
        URL.revokeObjectURL(url)
      } else {
        const res = await fetch('/api/v1/config/build', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ servers: hubIds }),
        })
        const blob = await res.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url; a.download = 'mcp-hub-config.json'; a.click()
        URL.revokeObjectURL(url)
      }
    } catch { setMessage('下载失败') }
    finally { setDownloading(false) }
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">⚙️ 我的配置</h1>
          <p className="text-sm text-gray-500 mt-1">管理你的 MCP Server 配置，下载后替换本地文件即可生效</p>
        </div>
        <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">去市场添加 →</Link>
      </div>

      {/* Upload */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-2">📤 上传本地配置</h2>
        <p className="text-sm text-gray-500 mb-3">上传你本地的 claude_desktop_config.json，Hub 自动识别并匹配市场中的 Server</p>
        <label className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 cursor-pointer transition-colors">
          📁 选择文件
          <input type="file" accept=".json" onChange={handleUpload} className="hidden" />
        </label>
      </div>

      {/* Server List */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">
            已跟踪的 Server <span className="text-gray-400 font-normal">({servers.length})</span>
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => { setServers([]); localStorage.removeItem('mcp_hub_my_servers'); setMessage('已清空') }}
              className="text-xs text-red-500 hover:text-red-700"
            >
              清空
            </button>
          </div>
        </div>

        {message && (
          <div className="mb-3 p-2 bg-blue-50 text-blue-700 rounded text-sm">{message}</div>
        )}

        {servers.length === 0 ? (
          <div className="text-center py-8 text-gray-400">
            <p>还没有添加任何 Server</p>
            <p className="text-sm mt-1">上传本地的配置文件，或去市场浏览添加</p>
            <Link to="/market" className="inline-block mt-3 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700">
              去市场浏览
            </Link>
          </div>
        ) : (
          <div className="space-y-2">
            {servers.map((s) => (
              <div key={s.name} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-800 truncate">{s.name}</span>
                    {s.matched ? (
                      <span className="text-xs px-1.5 py-0.5 bg-green-100 text-green-700 rounded">已匹配</span>
                    ) : (
                      <span className="text-xs px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded">未匹配</span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 truncate mt-0.5 font-mono">{s.command || '—'}</p>
                </div>
                <button onClick={() => removeServer(s.name)}
                  className="ml-2 px-2 py-1 text-xs text-red-500 hover:text-red-700 hover:bg-red-50 rounded transition-colors"
                >删除</button>
              </div>
            ))}
          </div>
        )}

        {servers.length > 0 && (
          <div className="mt-4 space-y-3">
            <button onClick={handleDownload} disabled={downloading}
              className="w-full py-3 bg-blue-600 text-white rounded-xl hover:bg-blue-700 font-medium transition-colors disabled:opacity-50">
              {downloading ? '生成中...' : '📥 下载完整配置 mcp-hub-config.json'}
            </button>
            <p className="text-xs text-gray-400 text-center">
              下载的配置包含你选择的所有 Server + Hub 网关入口，直接替换本地 claude_desktop_config.json 即可生效
            </p>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
              <p className="font-medium mb-1">替换后 Claude Code 将自动连接以下 Server：</p>
              <ul className="list-disc list-inside space-y-0.5">
                {servers.map(s => (
                  <li key={s.name}>{s.name}</li>
                ))}
                <li className="text-blue-600">mcp-hub-gateway（Hub 网关，聚合所有 Server）</li>
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
