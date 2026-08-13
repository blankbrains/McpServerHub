import { Link, useLocation } from 'react-router-dom'

const telemetryItems = [
  { path: '/devices', label: '设备与接入', matches: ['/devices'] },
  { path: '/inventory', label: '本地清单', matches: ['/inventory', '/local'] },
  { path: '/monitor', label: '运行监控', matches: ['/monitor'] },
  { path: '/analytics', label: '调用分析', matches: ['/analytics'] },
  { path: '/alerts', label: '告警', matches: ['/alerts', '/notifications'] },
  { path: '/reports', label: '报告', matches: ['/reports'] },
  { path: '/validation', label: '用户验证', matches: ['/validation'] },
] as const

function matchesRoute(pathname: string, prefixes: readonly string[]): boolean {
  return prefixes.some(prefix => pathname === prefix || pathname.startsWith(`${prefix}/`))
}

export default function TelemetryWorkspaceNav() {
  const location = useLocation()
  const visible = telemetryItems.some(item => matchesRoute(location.pathname, item.matches))

  if (!visible) return null

  return (
    <nav aria-label="设备与监控功能" className="mb-5 overflow-x-auto border-b border-gray-200 dark:border-gray-700">
      <div className="flex min-w-max gap-6">
        {telemetryItems.map(item => {
          const active = matchesRoute(location.pathname, item.matches)
          return (
            <Link
              key={item.path}
              to={item.path}
              aria-current={active ? 'page' : undefined}
              className={`flex h-10 items-center border-b-2 px-1 text-sm font-medium transition-colors ${
                active
                  ? 'border-blue-600 text-blue-700 dark:border-blue-400 dark:text-blue-300'
                  : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'
              }`}
            >
              {item.label}
            </Link>
          )
        })}
      </div>
    </nav>
  )
}
