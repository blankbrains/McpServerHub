import { Link } from 'react-router-dom'

const STEPS = [
  {
    num: 1,
    title: '准备你的 MCP 配置文件',
    icon: '📂',
    description: '从你的 AI Agent 中找到 MCP 配置文件',
    details: [
      { agent: 'Claude Code', path: '~/.config/Claude/claude_desktop_config.json' },
      { agent: 'Cursor', path: '~/.cursor/mcp.json' },
      { agent: 'Codex', path: '~/.codex/mcp.json' },
      { agent: 'Trae', path: '~/.trae/mcp.json' },
      { agent: 'Windsurf', path: '~/.windsurf/mcp.json' },
      { agent: 'VS Code Copilot', path: '~/.vscode/mcp.json' },
    ],
  },
  {
    num: 2,
    title: '上传配置到 Hub',
    icon: '📤',
    description: '在「配置中心」页面拖拽或点击上传你的 JSON 配置文件，Hub 会自动解析其中的 MCP Server 列表并展示预览。',
    action: { text: '前往配置中心 →', to: '/config' },
  },
  {
    num: 3,
    title: '检查 MCP 服务匹配结果',
    icon: '🔍',
    description: 'Hub 会自动在市场数据库中搜索你配置里的每个 MCP Server，并显示匹配/未匹配的结果：',
    highlights: [
      { label: '已匹配', desc: '在 Hub 市场中找到对应的 Server，自动关联版本、评分、安全等级等信息', color: 'green' },
      { label: '未匹配', desc: '未在市场找到的 Server 会被注册为自定义 Server，你仍可选择追踪', color: 'yellow' },
    ],
  },
  {
    num: 4,
    title: '决定是否上传到 Hub 进行监控',
    icon: '⚡',
    description: '这是关键步骤。Hub 提供两个选项：',
    highlights: [
      { label: '✅ 上传到 Hub', desc: '同意将你的 MCP Server 配置上传到 Hub。Hub 会持续追踪你的 Server 状态，并在监控大屏中展示调用次数、响应时长、Token 消耗等数据。', color: 'blue' },
      { label: '❌ 取消', desc: '不上传配置。Hub 不会记录或追踪你的任何 MCP 调用数据。你可以随时回来重新上传。', color: 'gray' },
    ],
  },
  {
    num: 5,
    title: '选择你的 AI Agent 工具',
    icon: '🎯',
    description: '选择你正在使用的 AI Agent（Claude Code / Cursor / Codex / Trae 等），Hub 会为该 Agent 生成匹配的配置文件格式，确保 MCP 调用能正确路由。',
  },
  {
    num: 6,
    title: '配置 MCP 网关以启用监控',
    icon: '📊',
    description: '要让 Hub 监控你的 MCP 调用，需要将 Hub 网关添加到你的 Agent 配置中。',
    code: `"mcp-hub-gateway": {
  "command": "mcp",
  "args": ["serve"]
}`,
    note: '将上述配置添加到你的 Agent MCP 配置文件的 mcpServers 中。添加后，所有 MCP 工具调用都会经过 Hub 网关，调用次数、响应时长、Token 消耗将自动记录。',
  },
  {
    num: 7,
    title: '查看监控数据',
    icon: '📈',
    description: '配置完成后，在 Hub 的监控大屏中可以实时查看所有 MCP Server 的运行状态和调用数据。',
    action: { text: '前往监控大屏 →', to: '/monitor' },
    subActions: [
      { text: '查看我的 Server →', to: '/my-servers' },
    ],
  },
]

export default function Guide() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-gray-900">📖 使用指南</h1>
        <p className="text-sm text-gray-500 mt-1">
          按照以下步骤，从上传配置到监控 MCP 调用，一步步完成设置
        </p>
      </div>

      {/* Step cards */}
      <div className="space-y-4">
        {STEPS.map((step) => (
          <div key={step.num} className="bg-white rounded-xl border border-gray-200 p-6 hover:border-gray-300 transition-colors">
            <div className="flex gap-4">
              {/* Step number */}
              <div className="flex-shrink-0">
                <span className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-blue-600 text-white font-bold text-lg">
                  {step.num}
                </span>
              </div>

              {/* Content */}
              <div className="flex-1 min-w-0 space-y-3">
                <h3 className="font-semibold text-gray-900 text-lg">
                  {step.icon} {step.title}
                </h3>
                <p className="text-sm text-gray-600">{step.description}</p>

                {/* Agent paths (Step 1) */}
                {step.details && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {step.details.map((d) => (
                      <div key={d.agent} className="bg-gray-50 rounded-lg p-3 border border-gray-100">
                        <p className="text-sm font-medium text-gray-800">{d.agent}</p>
                        <code className="text-xs text-gray-500 font-mono break-all">{d.path}</code>
                      </div>
                    ))}
                  </div>
                )}

                {/* Match highlights (Steps 3, 4) */}
                {step.highlights && (
                  <div className="space-y-2">
                    {step.highlights.map((h) => (
                      <div key={h.label} className={`rounded-lg p-3 border ${
                        h.color === 'green' ? 'bg-green-50 border-green-200' :
                        h.color === 'yellow' ? 'bg-yellow-50 border-yellow-200' :
                        h.color === 'blue' ? 'bg-blue-50 border-blue-200' :
                        'bg-gray-50 border-gray-200'
                      }`}>
                        <p className={`text-sm font-medium ${
                          h.color === 'green' ? 'text-green-800' :
                          h.color === 'yellow' ? 'text-yellow-800' :
                          h.color === 'blue' ? 'text-blue-800' :
                          'text-gray-600'
                        }`}>{h.label}</p>
                        <p className="text-xs text-gray-500 mt-0.5">{h.desc}</p>
                      </div>
                    ))}
                  </div>
                )}

                {/* Code block (Step 6) */}
                {step.code && (
                  <div className="bg-gray-900 rounded-lg p-4">
                    <pre className="text-green-400 text-sm font-mono whitespace-pre-wrap">
                      {step.code}
                    </pre>
                  </div>
                )}
                {step.note && (
                  <p className="text-xs text-gray-500">{step.note}</p>
                )}

                {/* Primary action button */}
                {step.action && (
                  <Link
                    to={step.action.to}
                    className="inline-flex items-center gap-1.5 px-5 py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 transition-colors"
                  >
                    {step.action.text}
                  </Link>
                )}

                {/* Sub actions */}
                {step.subActions && (
                  <div className="flex gap-2 flex-wrap">
                    {step.subActions.map((sa) => (
                      <Link
                        key={sa.to}
                        to={sa.to}
                        className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors"
                      >
                        {sa.text}
                      </Link>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick tips */}
      <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl border border-amber-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-3">💡 常见问题</h3>
        <div className="space-y-3 text-sm">
          <div>
            <p className="font-medium text-gray-800">Q: 上传配置后，Hub 能直接看到我本地的 MCP 调用吗？</p>
            <p className="text-gray-600 mt-0.5">
              A: 默认不能。你需要将 Hub 网关配置添加到本地 Agent 的 MCP 配置文件中。
              Hub 网关会作为中间人代理所有 MCP 调用，并自动记录调用数据到监控大屏。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: 「上传到 Hub」和「取消」有什么区别？</p>
            <p className="text-gray-600 mt-0.5">
              A: 选择「上传到 Hub」后，你的 MCP Server 列表和调用数据会被 Hub 追踪记录，
              你可以在监控大屏中查看统计。选择「取消」则不会记录任何数据，你的配置仅保存在本地。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: 我可以随时取消上传吗？</p>
            <p className="text-gray-600 mt-0.5">
              A: 是的。你可以在「我的 Server」或「配置」页面随时移除任何已追踪的 Server，
              也可以在配置页面点击「取消上传」来停止所有追踪。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: Hub 网关会影响 MCP Server 的性能吗？</p>
            <p className="text-gray-600 mt-0.5">
              A: Hub 网关以 stdio 方式运行在你的本地机器上，作为轻量代理转发请求。
              额外延迟通常 &lt; 5ms，对正常使用几乎没有影响。
            </p>
          </div>
        </div>
      </div>

      {/* Bottom CTA */}
      <div className="text-center py-4">
        <Link
          to="/config"
          className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors shadow-sm"
        >
          ⚡ 开始使用
        </Link>
      </div>
    </div>
  )
}
