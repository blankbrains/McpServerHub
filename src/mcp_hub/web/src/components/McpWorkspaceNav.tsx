import { Link, useLocation } from 'react-router-dom'

const workspaceItems = [
  { path: '/my-servers', label: '状态总览', icon: '📦', matches: ['/my-servers'] },
  { path: '/my-config', label: '配置与同步', icon: '⚙️', matches: ['/my-config', '/config'] },
  { path: '/local', label: '本地清单', icon: '🔍', matches: ['/local'] },
] as const

function matchesRoute(pathname: string, prefixes: readonly string[]): boolean {
  return prefixes.some(prefix => pathname === prefix || pathname.startsWith(`${prefix}/`))
}

export default function McpWorkspaceNav() {
  const location = useLocation()
  const visible = workspaceItems.some(item => matchesRoute(location.pathname, item.matches))

  if (!visible) return null

  return (
    <nav aria-label="我的 MCP 功能" className="mb-5 overflow-x-auto border-b border-gray-200 dark:border-gray-700">
      <div className="flex min-w-max gap-6">
        {workspaceItems.map(item => {
          const active = matchesRoute(location.pathname, item.matches)
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-current={active ? 'page' : undefined}
              className={`flex h-10 items-center gap-2 border-b-2 px-1 text-sm font-medium transition-colors ${
                active
                  ? 'border-blue-600 text-blue-700 dark:border-blue-400 dark:text-blue-300'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'
              }`}
            >
              <span aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
