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
  const [servers, setServers] = useState<ConfigServer[]>([])
  const [loading, setLoading] = useState(true)
  const [downloading, setDownloading] = useState(false)
  const [message, setMessage] = useState('')
  const userId = localStorage.getItem('mcp_hub_user')

  // 加载：优先从服务端，回退到 localStorage
  useEffect(() => {
    async function load() {
      try {
        const res = await fetch('/api/v1/config/user-servers', {
          headers: { 'x-user-id': userId || 'anonymous' }
        })
        const r = await res.json()
        if (r.success && r.data && r.data.length > 0) {
          setServers(r.data)
          localStorage.setItem('mcp_hub_my_servers', JSON.stringify(r.data))
          setLoading(false)
          return
        }
      } catch {}
      // 回退到 localStorage
      try {
        const local = JSON.parse(localStorage.getItem('mcp_hub_my_servers') || '[]')
        if (local.length > 0) setServers(local)
      } catch {}
      finally { setLoading(false) }
    }
    load()
  }, [])

  // 保存：同时写入 localStorage + 服务端
  useEffect(() => {
    localStorage.setItem('mcp_hub_my_servers', JSON.stringify(servers))
    if (!loading) {
      saveToServer(servers)
    }
  }, [servers, loading])

  async function saveToServer(srvList: ConfigServer[]) {
    try {
      await fetch('/api/v1/config/user-servers/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-user-id': userId || 'anonymous' },
        body: JSON.stringify({ servers: srvList }),
      })
    } catch {}
  }

  const removeServer = (name: string) => {
    if (!window.confirm(`确定要移除 "${name}" 吗？`)) return
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
    } catch (e) { setMessage('❌ 下载失败: ' + (e instanceof Error ? e.message : '')) }
    finally { setDownloading(false) }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64"><div className="text-gray-400 text-lg">加载配置中...</div></div>
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

      {/* Workflow Guide */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-5">
        <h2 className="font-semibold text-gray-900 mb-3">📋 完整工作流程</h2>
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-sm">
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">1</span>
            <p className="font-medium text-gray-800">上传配置</p>
            <p className="text-xs text-gray-500 mt-0.5">上传你本地的 claude_desktop_config.json，Hub 自动识别 Server</p>
          </div>
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">2</span>
            <p className="font-medium text-gray-800">浏览添加</p>
            <p className="text-xs text-gray-500 mt-0.5">在市场浏览，悬停 Server 卡片点击「+ 添加」</p>
          </div>
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">3</span>
            <p className="font-medium text-gray-800">下载配置</p>
            <p className="text-xs text-gray-500 mt-0.5">点击下方按钮下载完整的 mcp-hub-config.json</p>
          </div>
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">4</span>
            <p className="font-medium text-gray-800">覆盖本地</p>
            <p className="text-xs text-gray-500 mt-0.5">用下载的文件替换本地的 claude_desktop_config.json，重启 Claude Code 即可</p>
          </div>
        </div>
        <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
          <p className="font-medium">💡 监控说明</p>
          <p>替换配置并启动 Claude Code 后，MCP Server 会运行在你的本地机器上。
          Hub 的监控功能（健康检查、Token 分析、日志）需要在 daemon 模式下使用。</p>
        </div>
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
              onClick={() => { if (window.confirm('确定要清空所有配置吗？此操作不可撤销。')) { setServers([]); localStorage.removeItem('mcp_hub_my_servers'); setMessage('已清空') } }}
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
                    <input
                      type="text"
                      defaultValue={(s as any).group_name || ''}
                      placeholder="分组..."
                      onBlur={async (e) => {
                        const gname = e.target.value.trim()
                        if (!gname && !(s as any).group_name) return
                        const uid = localStorage.getItem('mcp_hub_user')
                        if (!uid) return
                        try {
                          await fetch('/api/v1/config/groups/set', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'x-user-id': uid },
                            body: JSON.stringify({ server_id: s.hub_id || s.name, group_name: gname }),
                          })
                        } catch {}
                      }}
                      className="px-1.5 py-0.5 text-xs border border-gray-200 rounded w-20 bg-white focus:ring-1 focus:ring-blue-400 outline-none"
                    />
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

        {/* CLI Sync Command */}
        {servers.length > 0 && (
          <div className="bg-gray-50 rounded-lg p-4 mt-4">
            <p className="text-sm font-medium text-gray-700 mb-2">🔄 一键同步到本地（CLI）</p>
            <p className="text-xs text-gray-500 mb-2">在你的本地机器上运行以下命令，自动下载配置并写入本地文件：</p>
            <div className="bg-gray-900 rounded-lg p-3 overflow-x-auto">
              <pre className="text-green-400 text-xs font-mono">
                {`mcp config sync --server ${window.location.origin}`}
              </pre>
            </div>
            <button onClick={() => {
              navigator.clipboard.writeText(`mcp config sync --server ${window.location.origin}`)
              setMessage('命令已复制到剪贴板')
              setTimeout(() => setMessage(''), 3000)
            }} className="mt-2 px-3 py-1.5 bg-gray-800 text-white rounded-lg text-xs hover:bg-gray-700 transition-colors">
              📋 复制命令
            </button>
            <p className="text-xs text-gray-400 mt-2">
              需要在本机安装 mcp-hub-cli 并已启动 Hub daemon。命令会自动将配置写入 ~/.config/Claude/claude_desktop_config.json
            </p>
          </div>
        )}
      </div>
    </div>
  )
}
