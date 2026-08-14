import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <section className="mx-auto max-w-3xl py-12 text-center" aria-labelledby="not-found-title">
      <p className="font-mono text-sm font-semibold text-gray-500">404</p>
      <h1 id="not-found-title" className="mt-2 text-2xl font-semibold text-gray-950 dark:text-white">
        页面不存在
      </h1>
      <p className="mt-2 text-sm text-gray-600 dark:text-gray-300">
        当前地址可能已失效，或者页面已移动到新的工作区。
      </p>
      <div className="mt-6 flex flex-wrap justify-center gap-3">
        <Link
          to="/"
          className="border border-gray-900 bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-700 dark:border-white dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
        >
          返回概览
        </Link>
        <Link
          to="/market"
          className="border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:border-gray-500 hover:text-gray-950 dark:border-gray-600 dark:text-gray-200 dark:hover:border-gray-400 dark:hover:text-white"
        >
          浏览 MCP 市场
        </Link>
      </div>
    </section>
  )
}
