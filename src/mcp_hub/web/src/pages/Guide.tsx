import { Link } from 'react-router-dom'

const CLI_INSTALL_COMMAND = 'uv tool install --force "git+https://github.com/blankbrains/McpServerHub.git@main"'
const WINDOWS_D_DRIVE_INSTALL_COMMAND = `[Environment]::SetEnvironmentVariable("UV_TOOL_DIR", "D:\\uv\\tools", "User")
[Environment]::SetEnvironmentVariable("UV_TOOL_BIN_DIR", "D:\\uv\\bin", "User")
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "D:\\uv\\cache", "User")
[Environment]::SetEnvironmentVariable("UV_PYTHON_INSTALL_DIR", "D:\\uv\\python", "User")`
const CLI_UNINSTALL_COMMAND = `uv tool list --show-paths
uv tool uninstall mcp-hub-cli
where.exe mcp-hub`

interface GuideStep {
  num: number
  title: string
  icon: string
  description: string
  details?: Array<{ agent: string; path: string }>
  code?: string
  note?: string
  action?: { text: string; to: string }
}

function buildSteps(hubUrl: string): GuideStep[] {
  return [
    {
      num: 1,
      title: '确认运行方式',
      icon: '🧭',
      description: '网页 Hub 运行在服务器上；mcp-hub CLI、Gateway、AI Agent 和 MCP Server 运行在你的电脑上。服务器不能主动读取你的本地调用，必须由本地 Gateway 代理并上报指标。',
    },
    {
      num: 2,
      title: '安装 uv 和 mcp-hub CLI',
      icon: '⬇️',
      description: '当前 0.2.0 尚未发布到 PyPI，请从 GitHub 安装。这一步只在你的电脑上安装 CLI 和本地 Gateway，不会修改 Hub 服务器、GitHub 仓库或项目代码。运行 uv tool update-shell 后必须关闭并重新打开终端。',
      code: `${CLI_INSTALL_COMMAND}
uv tool update-shell
mcp-hub --version`,
      note: '仅切换到 D 盘后运行命令不会改变安装位置。uv 默认安装到用户目录；Windows 如需把工具、命令入口、缓存和 uv 管理的 Python 放到 D 盘，请先按下方“安装位置与卸载”设置目录。',
    },
    {
      num: 3,
      title: '确认电脑可以访问 Hub',
      icon: '🌐',
      description: '在运行 Agent 的同一台电脑上检查 Hub 健康接口。返回 status 为 healthy 才继续；无法访问时先处理局域网、VPN、防火墙或服务器地址问题。',
      code: `curl ${hubUrl}/api/v1/health`,
    },
    {
      num: 4,
      title: '准备现有 Agent MCP 配置',
      icon: '📂',
      description: 'agent setup 负责迁移已有连接，不负责替你创建第一个 MCP Server。先确认目标 Agent 已至少配置一个可用的 stdio、Streamable HTTP 或 SSE Server。',
      details: [
        { agent: 'Claude Code', path: '~/.claude.json 或项目 .mcp.json' },
        { agent: 'Claude Desktop', path: 'Claude/claude_desktop_config.json' },
        { agent: 'Cursor', path: '~/.cursor/mcp.json' },
        { agent: 'Codex', path: '~/.codex/config.toml' },
        { agent: 'Trae', path: '~/.trae/mcp.json' },
        { agent: 'Windsurf', path: '~/.codeium/windsurf/mcp_config.json' },
        { agent: 'VS Code Copilot', path: '.vscode/mcp.json' },
      ],
      note: '网页配置上传仅支持根节点为 mcpServers 的 JSON。Codex config.toml 使用 mcp_servers，VS Code Copilot mcp.json 使用 servers；这两类配置请直接使用 agent setup 自动识别、预览和迁移。',
    },
    {
      num: 5,
      title: '登录网页并创建设备',
      icon: '🔐',
      description: '在网页完成 GitHub 登录，进入监控页，选择实际使用的 Agent 并创建设备。每个 Agent 应使用独立设备令牌；令牌只显示一次，不要截图、提交到 Git 或发送给他人。',
      action: { text: '前往监控页创建设备 →', to: '/monitor' },
    },
    {
      num: 6,
      title: '运行页面生成的接入命令',
      icon: '📊',
      description: '在监控页复制包含真实设备令牌的完整命令并在本地终端运行。下面只是格式示例，不要照抄示例令牌。',
      code: `mcp-hub agent setup --agent codex --hub-url ${hubUrl} --telemetry-token mcpht_设备令牌`,
      note: 'CLI 会展示迁移预览。确认后才会备份原 Agent 配置、写入独立 gateway.json，并用 mcp-hub serve 替换可代理的直接连接；不支持的条目会保留。',
    },
    {
      num: 7,
      title: '完全重启 Agent',
      icon: '🔁',
      description: '退出所有目标 Agent 进程后重新打开。仅关闭当前对话或刷新窗口通常不够；Agent 必须重新读取已经写入的 MCP 配置，并且新进程的 PATH 中必须能找到 mcp-hub。',
    },
    {
      num: 8,
      title: '触发一次真实 MCP 工具调用',
      icon: '🧪',
      description: '让 Agent 实际调用一个已迁移 Server 的工具。只启动 Agent、查看工具列表或普通对话不会产生 tool_call 监控数据。',
    },
    {
      num: 9,
      title: '刷新监控并核对数据',
      icon: '📈',
      description: '回到监控页刷新，检查设备最后在线时间、Server 调用数、工具调用、延迟、错误和估算 Token。Token 是 Gateway 根据载荷估算的值，不等于模型供应商账单。',
      action: { text: '前往监控大屏 →', to: '/monitor' },
    },
    {
      num: 10,
      title: '运行端到端接入验证',
      icon: '🩺',
      description: 'verify 会一次检查 Agent 入口、Gateway 配置、本地命令与队列、Hub 网络、设备令牌、Gateway 心跳和首次真实工具调用，并给出稳定错误码。',
      code: `mcp-hub agent verify --agent codex
mcp-hub agent verify --agent codex --json`,
      note: '默认验证只读。需要修复时使用 --fix，CLI 会先展示预览；配置写入前自动备份，冲突配置和缺失令牌不会被猜测修复。网络中断时，遥测事件仍保留在本地 SQLite 队列中。',
    },
  ]
}

export default function Guide() {
  const steps = buildSteps(window.location.origin)

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="mb-2">
        <h1 className="text-2xl font-bold text-gray-900">📖 使用指南</h1>
        <p className="text-sm text-gray-500 mt-1">
          按照以下步骤，在本地接入 Gateway 并验证第一条 MCP 监控数据
        </p>
      </div>

      {/* Step cards */}
      <div className="space-y-4">
        {steps.map((step) => (
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

                {/* Commands */}
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

              </div>
            </div>
          </div>
        ))}
      </div>

      <section className="border-y border-gray-200 py-6">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">安装位置与卸载</h2>
          <p className="mt-1 text-sm text-gray-600">
            以下操作只影响当前电脑上的 uv 和 mcp-hub CLI，不会修改远程 Hub、生产服务或项目源码。
          </p>
        </div>

        <div className="mt-5 grid gap-6 lg:grid-cols-2">
          <div className="min-w-0">
            <h3 className="font-medium text-gray-900">Windows 安装到 D 盘</h3>
            <p className="mt-1 text-sm text-gray-600">
              在 PowerShell 中保存这些用户环境变量，关闭并重新打开终端后，再执行上面的安装命令。
              当前终端所在目录不会决定 uv 的安装位置。
            </p>
            <div className="mt-3 bg-gray-900 rounded-lg p-4">
              <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap break-all">
                {WINDOWS_D_DRIVE_INSTALL_COMMAND}
              </pre>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              安装后可使用 uv tool dir、uv tool dir --bin、uv python dir 和 where.exe mcp-hub 核对实际路径。
            </p>
          </div>

          <div className="min-w-0">
            <h3 className="font-medium text-gray-900">卸载 mcp-hub CLI</h3>
            <p className="mt-1 text-sm text-gray-600">
              如果使用了自定义目录，卸载时必须保留相同的 UV_TOOL_DIR 和 UV_TOOL_BIN_DIR，
              让 uv 能找到对应安装。
            </p>
            <div className="mt-3 bg-gray-900 rounded-lg p-4">
              <pre className="text-green-400 text-xs font-mono whitespace-pre-wrap break-all">
                {CLI_UNINSTALL_COMMAND}
              </pre>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              卸载只删除 mcp-hub-cli 的工具环境和命令入口，不会卸载 uv，也不会自动恢复已经写入 Agent 的 MCP 配置。
            </p>
          </div>
        </div>
      </section>

      {/* Quick tips */}
      <div className="bg-gradient-to-br from-amber-50 to-orange-50 rounded-xl border border-amber-200 p-6">
        <h3 className="font-semibold text-gray-900 mb-3">💡 常见问题</h3>
        <div className="space-y-3 text-sm">
          <div>
            <p className="font-medium text-gray-800">Q: 网页配置上传支持哪些文件？</p>
            <p className="text-gray-600 mt-0.5">
              A: 仅支持 JSON，且 MCP Server 必须位于根节点 <code className="font-mono">mcpServers</code>。
              Codex 的 <code className="font-mono">config.toml</code> 和 VS Code Copilot 根节点为
              <code className="mx-1 font-mono">servers</code>的配置不要直接上传，请使用 agent setup 自动迁移。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: 保存追踪后，Hub 能直接看到我本地的 MCP 调用吗？</p>
            <p className="text-gray-600 mt-0.5">
              A: 默认不能。你需要在监控页创建设备并运行 agent setup，让本地 Gateway 代理 Agent 与 MCP Server 的通信。
              Agent 直接连接 Server 的调用不会经过 Hub，也不会出现在监控页。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: 为什么已经创建设备，监控页仍然没有调用？</p>
            <p className="text-gray-600 mt-0.5">
              A: 创建设备只生成上报凭证。还必须运行 agent setup、完全重启 Agent，并实际调用一次经过 Gateway 的 MCP 工具。
              直接连接 Server 的调用、普通聊天和仅查看工具列表都不会产生监控数据。运行
              <code className="mx-1 font-mono">mcp-hub agent verify --agent &lt;agent&gt;</code>
              可以明确区分网络、令牌、Gateway 心跳、首次调用和队列问题。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: 为什么页面提示自动复制失败？</p>
            <p className="text-gray-600 mt-0.5">
              A: HTTP 页面可能被浏览器限制剪贴板权限。系统会尝试兼容复制；如果浏览器仍拒绝，
              命令会完整显示在页面中，可以直接选中后按 Ctrl+C，macOS 使用 Cmd+C。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: 「确认追踪」和「取消」有什么区别？</p>
            <p className="text-gray-600 mt-0.5">
              A: 选择「确认追踪」后，Server 会保存到你的个人追踪列表。选择「取消」不会保存本次检查结果。
              MCP 调用统计仅在本地 Gateway 接入并代理真实调用后才会产生。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: 我可以随时停止追踪吗？</p>
            <p className="text-gray-600 mt-0.5">
              A: 是的。你可以在「我的 Server」或「配置」页面随时移除任何已追踪的 Server，
              也可以停止整份追踪列表；这些操作不会卸载或停止本地进程。
            </p>
          </div>
          <div>
            <p className="font-medium text-gray-800">Q: Hub 网关会影响 MCP Server 的性能吗？</p>
            <p className="text-gray-600 mt-0.5">
              A: 本地 Gateway 通过 stdio 接入 Agent，并可代理 stdio、Streamable HTTP 和 SSE Server。
              实际开销取决于 Server、网络、工具调用和本机资源，接入后应通过监控页的真实调用数据评估。
            </p>
          </div>
        </div>
      </div>

      {/* Bottom CTA */}
      <div className="text-center py-4">
        <Link
          to="/monitor"
          className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 text-white rounded-xl font-medium hover:bg-blue-700 transition-colors shadow-sm"
        >
          📊 前往监控页
        </Link>
      </div>
    </div>
  )
}
