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
  const [trackingStatus, setTrackingStatus] = useState<'idle' | 'uploaded' | 'cancelled'>('idle')
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
          setTrackingStatus('uploaded')
          localStorage.setItem('mcp_hub_my_servers', JSON.stringify(r.data))
          setLoading(false)
          return
        }
      } catch {}
      // 回退到 localStorage
      try {
        const local = JSON.parse(localStorage.getItem('mcp_hub_my_servers') || '[]')
        if (local.length > 0) {
          setServers(local)
          setTrackingStatus('uploaded')
        }
      } catch {}
      finally { setLoading(false) }
    }
    load()
  }, [])

  // 保存：同时写入 localStorage + 服务端
  const saveToServer = async (srvList: ConfigServer[]) => {
    try {
      await fetch('/api/v1/config/user-servers/save', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-user-id': userId || 'anonymous' },
        body: JSON.stringify({ servers: srvList }),
      })
    } catch {}
  }

  const removeServer = async (name: string) => {
    if (!window.confirm(`确定要移除 "${name}" 吗？`)) return
    setServers(prev => prev.filter(s => s.name !== name))
    // 同步删除服务器上的记录
    try {
      const uid = localStorage.getItem('mcp_hub_user') || 'anonymous'
      await fetch(`/api/v1/config/user-servers/${encodeURIComponent(name)}`, {
        method: 'DELETE',
        headers: { 'x-user-id': uid },
      })
    } catch {}
    setMessage(`已移除 ${name}`)
    setTimeout(() => setMessage(''), 3000)
  }

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    try {
      const form = new FormData()
      form.append('file', file)
      const res = await fetch('/api/v1/config/upload', {
        method: 'POST',
        body: form,
        headers: { 'x-user-id': localStorage.getItem('mcp_hub_user') || 'anonymous' },
      })
      const result = await res.json()
      if (result.success && result.data) {
        const { matched, unmatched } = result.data
        const seen = new Set(servers.map(s => s.name))
        const newServers: ConfigServer[] = []
        for (const m of (matched || [])) {
          if (!seen.has(m.local_name)) {
            seen.add(m.local_name)
            newServers.push({
              name: m.hub_id || m.local_name,
              command: m.hub_install_command || m.local_command,
              hub_id: m.hub_id,
              matched: true,
            })
          }
        }
        for (const u of (unmatched || [])) {
          if (!seen.has(u.local_name)) {
            seen.add(u.local_name)
            newServers.push({
              name: u.local_name,
              command: u.local_command,
              matched: false,
            })
          }
        }
        if (newServers.length > 0) {
          const merged = [...servers, ...newServers]
          setServers(merged)
          localStorage.setItem('mcp_hub_my_servers', JSON.stringify(merged))
          setMessage(`已检测到 ${newServers.length} 个 Server，请选择是否上传到 Hub 进行监控`)
          // 重置为 idle，让用户主动选择上传或取消
          setTrackingStatus('idle')
        } else {
          setMessage('所有 Server 已在列表中')
        }
      } else {
        setMessage(result.error || '上传失败')
      }
    } catch {
      setMessage('上传失败')
    }
    setTimeout(() => setMessage(''), 5000)
  }

  // === 上传到 Hub：确认追踪 ===
  const handleUploadToHub = async () => {
    if (servers.length === 0) return
    await saveToServer(servers)
    setTrackingStatus('uploaded')
    setMessage('✅ 已上传到 Hub！你的 MCP Server 将被持续监控')
    setTimeout(() => setMessage(''), 4000)
  }

  // === 取消上传：从 Hub 移除所有追踪 ===
  const handleCancelTracking = async () => {
    if (!window.confirm('确定要取消上传吗？Hub 将不再追踪你的 MCP Server 配置和调用数据。')) return
    // 从服务端清除
    try {
      for (const s of servers) {
        const sid = s.hub_id || s.name
        await fetch(`/api/v1/config/user-servers/${encodeURIComponent(sid)}`, {
          method: 'DELETE',
          headers: { 'x-user-id': userId || 'anonymous' },
        })
      }
    } catch {}
    setServers([])
    localStorage.removeItem('mcp_hub_my_servers')
    setTrackingStatus('cancelled')
    setMessage('已取消上传，你的配置信息已从 Hub 中移除')
    setTimeout(() => setMessage(''), 4000)
  }

  const handleDownload = async () => {
    if (servers.length === 0) return
    setDownloading(true)
    try {
      const hubIds = servers
        .filter(s => s.matched && s.hub_id)
        .map(s => s.hub_id as string)

      if (hubIds.length === 0) {
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
        if (!res.ok) throw new Error(`服务器错误: ${res.status}`)
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
          <p className="text-sm text-gray-500 mt-1">上传你的 MCP 配置文件，选择是否上传到 Hub 进行监控</p>
        </div>
        <Link to="/market" className="text-sm text-blue-600 hover:text-blue-800">去市场添加 →</Link>
      </div>

      {/* Workflow Guide */}
      <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-200 p-5">
        <h2 className="font-semibold text-gray-900 mb-3">📋 操作流程</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-sm">
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">1</span>
            <p className="font-medium text-gray-800">上传配置</p>
            <p className="text-xs text-gray-500 mt-0.5">上传你本地的 MCP 配置文件，Hub 自动识别并匹配 Server</p>
          </div>
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">2</span>
            <p className="font-medium text-gray-800">上传 / 取消</p>
            <p className="text-xs text-gray-500 mt-0.5">选择是否将配置上传到 Hub 以启用监控追踪</p>
          </div>
          <div className="bg-white rounded-lg p-3 border border-blue-100">
            <span className="inline-flex items-center justify-center w-6 h-6 rounded-full bg-blue-600 text-white text-xs font-bold mb-1">3</span>
            <p className="font-medium text-gray-800">下载配置</p>
            <p className="text-xs text-gray-500 mt-0.5">下载更新后的配置，替换本地文件，重启 Agent 即可生效</p>
          </div>
        </div>
        <div className="mt-3 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-xs text-yellow-800">
          <p className="font-medium">💡 说明</p>
          <p>选择「上传到 Hub」后，Hub 会记录你的 MCP Server 列表。当你通过 Hub 网关调用 MCP 时，调用次数、响应时长等数据会自动记录到监控大屏。选择「取消」则不会被追踪。</p>
        </div>
      </div>

      {/* Upload */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-2">📤 步骤 1：上传本地 MCP 配置</h2>
        <p className="text-sm text-gray-500 mb-3">
          上传 <code className="px-1 bg-gray-100 rounded text-xs">claude_desktop_config.json</code> 或 <code className="px-1 bg-gray-100 rounded text-xs">mcp.json</code>，Hub 自动识别并匹配市场中的 Server
        </p>
        <div className="flex gap-2">
          <label className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 cursor-pointer transition-colors">
            📁 选择文件
            <input type="file" accept=".json" onChange={handleUpload} className="hidden" />
          </label>
          <Link to="/config" className="inline-flex items-center gap-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors">
            完整配置中心 →
          </Link>
        </div>
      </div>

      {/* ── 上传/取消决策区 ── */}
      {servers.length > 0 && (
        <div className={`rounded-xl border-2 p-6 ${
          trackingStatus === 'uploaded' ? 'bg-green-50 border-green-300' :
          trackingStatus === 'cancelled' ? 'bg-gray-50 border-gray-300' :
          'bg-amber-50 border-amber-300'
        }`}>
          <h2 className="font-semibold text-gray-900 mb-2">⚡ 步骤 2：是否上传到 Hub 进行监控？</h2>

          {trackingStatus === 'uploaded' ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-green-600 text-white rounded-full text-sm font-medium">
                  ✅ 已上传到 Hub
                </span>
                <span className="text-sm text-green-700">你的 {servers.length} 个 MCP Server 正在被 Hub 追踪监控</span>
              </div>
              <p className="text-sm text-green-700">
                当你的 Agent 通过 Hub 网关调用 MCP 时，调用数据（次数、响应时长、Token 消耗）会自动记录。
              </p>
              <button
                onClick={handleCancelTracking}
                className="px-5 py-2 bg-white text-red-600 border border-red-300 rounded-lg text-sm font-medium hover:bg-red-50 transition-colors"
              >
                ❌ 取消上传（停止追踪）
              </button>
            </div>
          ) : trackingStatus === 'cancelled' ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-gray-400 text-white rounded-full text-sm font-medium">
                  已取消上传
                </span>
                <span className="text-sm text-gray-500">Hub 不会追踪你的 MCP 配置和调用数据</span>
              </div>
              <p className="text-sm text-gray-500">
                你的 {servers.length} 个 Server 仍在本地列表中。你可以随时重新上传到 Hub。
              </p>
              <button
                onClick={handleUploadToHub}
                className="px-5 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
              >
                ✅ 重新上传到 Hub
              </button>
            </div>
          ) : (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1 px-3 py-1 bg-amber-500 text-white rounded-full text-sm font-medium">
                  ⚠️ 待确认
                </span>
                <span className="text-sm text-amber-700">检测到 {servers.length} 个 MCP Server，请选择</span>
              </div>
              <p className="text-sm text-amber-700">
                上传后，Hub 会记录你的 Server 列表并监控调用数据。你也可以随时取消。
              </p>
              <div className="flex gap-3">
                <button
                  onClick={handleUploadToHub}
                  className="px-6 py-2.5 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
                >
                  ✅ 上传到 Hub
                </button>
                <button
                  onClick={handleCancelTracking}
                  className="px-6 py-2.5 bg-white text-gray-600 border border-gray-300 rounded-lg text-sm font-medium hover:bg-gray-50 transition-colors"
                >
                  ❌ 取消
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Server List */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-semibold text-gray-900">
            已跟踪的 Server <span className="text-gray-400 font-normal">({servers.length})</span>
          </h2>
          <div className="flex gap-2">
            <button
              onClick={() => { if (window.confirm('确定要清空所有配置吗？此操作不可撤销。')) { setServers([]); localStorage.removeItem('mcp_hub_my_servers'); setTrackingStatus('cancelled'); setMessage('已清空') } }}
              className="text-xs text-red-500 hover:text-red-700"
            >
              清空
            </button>
          </div>
        </div>

        {message && (
          <div className={`mb-3 p-2 rounded text-sm ${
            message.startsWith('✅') ? 'bg-green-50 text-green-700' :
            message.startsWith('❌') ? 'bg-red-50 text-red-700' :
            'bg-blue-50 text-blue-700'
          }`}>{message}</div>
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
                          const gr = await fetch('/api/v1/config/groups/set', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'x-user-id': uid },
                            body: JSON.stringify({ server_id: s.hub_id || s.name, group_name: gname }),
                          })
                          if (!gr.ok) throw new Error('save failed')
                          setMessage('✅ 分组已更新')
                          setTimeout(() => setMessage(''), 2000)
                        } catch { setMessage('⚠️ 分组保存失败') }
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
              className="w-full py-3 bg-gray-800 text-white rounded-xl hover:bg-gray-900 font-medium transition-colors disabled:opacity-50">
              {downloading ? '生成中...' : '📥 下载配置文件（用于替换本地 Agent 配置）'}
            </button>
            <p className="text-xs text-gray-400 text-center">
              下载的配置包含你选择的所有 Server + Hub 网关入口，替换本地 Agent 配置文件并重启后生效
            </p>
            <div className="bg-gray-50 rounded-lg p-3 text-xs text-gray-500">
              <p className="font-medium mb-1">替换后 Agent 将自动连接以下 Server：</p>
              <ul className="list-disc list-inside space-y-0.5">
                {servers.map(s => (
                  <li key={s.name}>{s.name}</li>
                ))}
                <li className="text-blue-600">mcp-hub-gateway（Hub 网关，用于自动监控）</li>
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

      {/* 配置草稿 */}
      <ConfigDrafts servers={servers} onLoad={(s) => { setServers(s); localStorage.setItem('mcp_hub_my_servers', JSON.stringify(s)); setMessage('✅ 已加载草稿'); setTimeout(() => setMessage(''), 2000) }} />
    </div>
  )
}

function ConfigDrafts({ servers, onLoad }: { servers: ConfigServer[], onLoad: (s: ConfigServer[]) => void }) {
  const [drafts, setDrafts] = useState<{ name: string; servers: ConfigServer[]; savedAt: string }[]>(() => {
    try { return JSON.parse(localStorage.getItem('mcp_hub_drafts') || '[]') } catch { return [] }
  })
  const [draftName, setDraftName] = useState('')

  const saveDraft = () => {
    if (!draftName.trim() || servers.length === 0) return
    const existing = drafts.filter(d => d.name !== draftName.trim())
    const updated = [...existing, { name: draftName.trim(), servers, savedAt: new Date().toISOString().slice(0, 16) }]
    setDrafts(updated)
    localStorage.setItem('mcp_hub_drafts', JSON.stringify(updated))
    setDraftName('')
  }

  const deleteDraft = (name: string) => {
    const updated = drafts.filter(d => d.name !== name)
    setDrafts(updated)
    localStorage.setItem('mcp_hub_drafts', JSON.stringify(updated))
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-6">
      <h2 className="font-semibold text-gray-900 mb-3">💾 配置草稿</h2>
      <p className="text-xs text-gray-500 mb-3">保存当前 Server 配置为草稿，方便在不同配置方案间快速切换</p>

      {/* 保存草稿 */}
      <div className="flex gap-2 mb-4">
        <input type="text" value={draftName} onChange={e => setDraftName(e.target.value)}
          placeholder="草稿名称（如：工作用/个人用）"
          className="flex-1 px-3 py-1.5 text-xs border border-gray-300 rounded-lg focus:ring-1 focus:ring-blue-400 outline-none" />
        <button onClick={saveDraft} disabled={servers.length === 0 || !draftName.trim()}
          className="px-4 py-1.5 bg-blue-600 text-white rounded-lg text-xs font-medium hover:bg-blue-700 disabled:opacity-50">
          保存草稿
        </button>
      </div>

      {/* 草稿列表 */}
      {drafts.length === 0 ? (
        <p className="text-xs text-gray-400">暂存配置草稿，方便快速切换</p>
      ) : (
        <div className="space-y-1.5">
          {drafts.map(d => (
            <div key={d.name} className="flex items-center justify-between p-2 bg-gray-50 rounded-lg text-xs">
              <div>
                <span className="font-medium text-gray-700">{d.name}</span>
                <span className="text-gray-400 ml-2">{d.servers.length} 个 Server</span>
                <span className="text-gray-300 ml-2">{d.savedAt}</span>
              </div>
              <div className="flex gap-1.5">
                <button onClick={() => { if (window.confirm(`加载草稿"${d.name}"将替换当前配置，确定？`)) onLoad(d.servers) }}
                  className="px-2 py-0.5 bg-green-100 text-green-700 rounded hover:bg-green-200">加载</button>
                <button onClick={() => { if (window.confirm('确定删除此草稿？')) deleteDraft(d.name) }}
                  className="px-2 py-0.5 text-red-400 hover:text-red-600 hover:bg-red-50 rounded">删除</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
