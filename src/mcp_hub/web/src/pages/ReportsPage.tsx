import { useState } from 'react'
import { Link } from 'react-router-dom'
import { exportTelemetryReport } from '../api/client'
import AuthRequired from '../components/AuthRequired'
import { useAuthState } from '../hooks/useAuthState'

export default function ReportsPage() {
  const auth = useAuthState()
  const [exporting, setExporting] = useState(false)
  const [error, setError] = useState('')
  const authenticated = Boolean(auth.token)

  const exportReport = async () => {
    if (!authenticated) {
      setError('请先登录后导出当前账户的遥测报告。')
      return
    }

    setExporting(true)
    setError('')
    try {
      const blob = await exportTelemetryReport(7)
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url
      anchor.download = 'mcp-hub-telemetry-report-7d.json'
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      URL.revokeObjectURL(url)
    } catch {
      setError('遥测报告导出失败，请检查登录状态后重试。')
    } finally {
      setExporting(false)
    }
  }

  if (!authenticated) {
    return (
      <AuthRequired
        title="登录后导出遥测报告"
        description="报告聚合当前账户授权设备的调用、性能和错误指标，登录后才能生成和下载。"
      />
    )
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-gray-900">报告</h1>
        <p className="mt-1 text-sm text-gray-500">导出当前账户最近 7 天的本地 Gateway 遥测汇总。</p>
      </header>

      {error && <div role="alert" className="border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      <section className="border border-gray-200 bg-white p-5" aria-labelledby="telemetry-report-title">
        <h2 id="telemetry-report-title" className="text-base font-semibold text-gray-900">遥测报告</h2>
        <p className="mt-2 text-sm text-gray-600">
          报告包含已授权设备上报的聚合调用、性能和错误指标，不包含原始请求或响应内容。
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            type="button"
            onClick={() => void exportReport()}
            disabled={exporting}
            className="rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {exporting ? '导出中...' : '导出报告'}
          </button>
          <Link to="/analytics" className="rounded-md border border-gray-300 px-4 py-2 text-sm text-gray-700 hover:bg-gray-50">
            查看调用分析
          </Link>
        </div>
      </section>
    </div>
  )
}
