import { useEffect, useRef, useState } from 'react'
import { connectLogSSE } from '../api/client'

interface LogViewerProps {
  serverId: string
  maxLines?: number
  autoScroll?: boolean
  className?: string
}

export default function LogViewer({
  serverId,
  maxLines = 200,
  autoScroll = true,
  className = '',
}: LogViewerProps) {
  const [lines, setLines] = useState<string[]>([])
  const [connected, setConnected] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const esRef = useRef<EventSource | null>(null)

  useEffect(() => {
    // 从 REST API 加载初始日志
    fetch(`/api/v1/servers/${encodeURIComponent(serverId)}/logs?lines=${maxLines}`)
      .then(res => res.json())
      .then(data => {
        if (data.success && data.data) {
          setLines(data.data.map((l: string) => l.replace(/\n$/, '')))
        }
      })
      .catch(() => {
        // 无日志文件时不报错
      })

    // 连接 SSE 实时日志流
    const es = connectLogSSE(serverId, (line: string) => {
      setConnected(true)
      setLines(prev => {
        const next = [...prev, line.replace(/\n$/, '')]
        if (next.length > maxLines) {
          return next.slice(next.length - maxLines)
        }
        return next
      })
    })

    es.onopen = () => setConnected(true)
    es.onerror = () => setConnected(false)
    esRef.current = es

    return () => {
      es.close()
      setConnected(false)
    }
  }, [serverId, maxLines])

  // 自动滚动到底部
  useEffect(() => {
    if (autoScroll && containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [lines, autoScroll])

  return (
    <div className={`flex flex-col ${className}`}>
      {/* 工具栏 */}
      <div className="flex items-center justify-between px-3 py-2 bg-gray-900 rounded-t-lg border-b border-gray-700">
        <div className="flex items-center gap-2">
          <span role="img" aria-label={connected ? '已连接' : '已断开'} className={`w-2 h-2 rounded-full ${connected ? 'bg-green-400' : 'bg-red-400'}`} />
          <span className="text-xs text-gray-400 font-mono">{serverId}</span>
        </div>
        <span className="text-xs text-gray-500">
          {lines.length} 行{connected ? ' · 实时' : ''}
        </span>
      </div>

      {/* 日志内容 */}
      <div
        ref={containerRef}
        role="log"
        aria-live="polite"
        className="bg-gray-950 text-gray-200 font-mono text-xs leading-relaxed p-3 rounded-b-lg overflow-auto max-h-80"
      >
        {lines.length === 0 ? (
          <div className="text-gray-500 text-center py-8">
            <p>暂无日志输出</p>
            <p className="mt-1 text-gray-600">启动 Server 后将在此显示实时日志</p>
          </div>
        ) : (
          lines.map((line, i) => (
            <div
              key={i}
              className={`whitespace-pre-wrap break-all ${
                line.includes('ERROR') || line.includes('error')
                  ? 'text-red-400'
                  : line.includes('WARN') || line.includes('warn')
                  ? 'text-yellow-400'
                  : 'text-green-300/80'
              }`}
            >
              {line}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
