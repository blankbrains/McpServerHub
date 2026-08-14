import { Link } from 'react-router-dom'

interface AuthRequiredProps {
  title: string
  description: string
}

export default function AuthRequired({ title, description }: AuthRequiredProps) {
  return (
    <section className="mx-auto max-w-3xl py-8" aria-labelledby="auth-required-title">
      <div className="border-y border-gray-200 bg-white py-12 text-center dark:border-gray-700 dark:bg-gray-900">
        <p className="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">
          需要登录
        </p>
        <h1 id="auth-required-title" className="mt-2 text-xl font-semibold text-gray-950 dark:text-white">
          {title}
        </h1>
        <p className="mx-auto mt-2 max-w-xl px-4 text-sm leading-6 text-gray-600 dark:text-gray-300">
          {description}
        </p>
        <Link
          to="/login"
          className="mt-6 inline-flex items-center border border-gray-900 bg-gray-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2 dark:border-white dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
        >
          前往 GitHub 登录
        </Link>
      </div>
    </section>
  )
}
