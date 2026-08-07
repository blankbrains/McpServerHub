import { type ReactNode, useId } from 'react'

interface InfoTooltipProps {
  children: ReactNode
  description: string
  align?: 'start' | 'end'
  side?: 'above' | 'below'
}

export default function InfoTooltip({
  children,
  description,
  align = 'start',
  side = 'above',
}: InfoTooltipProps) {
  const descriptionId = useId()
  const position = align === 'end' ? 'right-0' : 'left-0'
  const verticalPosition = side === 'below' ? 'top-full mt-2' : 'bottom-full mb-2'

  return (
    <span className="group relative inline-flex">
      <span
        tabIndex={0}
        aria-describedby={descriptionId}
        className="cursor-help border-b border-dotted border-current/40 outline-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {children}
      </span>
      <span
        id={descriptionId}
        role="tooltip"
        className={`pointer-events-none absolute ${position} ${verticalPosition} z-30 w-64 max-w-[calc(100vw-2rem)] rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-xs leading-5 text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-within:opacity-100`}
      >
        {description}
      </span>
    </span>
  )
}
