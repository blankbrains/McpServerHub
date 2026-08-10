import {
  type ReactNode,
  useCallback,
  useId,
  useLayoutEffect,
  useRef,
  useState,
} from 'react'
import { createPortal } from 'react-dom'

interface InfoTooltipProps {
  children: ReactNode
  description: string
  align?: 'start' | 'end'
  side?: 'above' | 'below'
}

interface TooltipPosition {
  left: number
  top: number
  width: number
}

const VIEWPORT_PADDING = 16
const TOOLTIP_GAP = 8
const TOOLTIP_WIDTH = 256

export default function InfoTooltip({
  children,
  description,
  align = 'start',
  side = 'above',
}: InfoTooltipProps) {
  const descriptionId = useId()
  const triggerRef = useRef<HTMLSpanElement>(null)
  const tooltipRef = useRef<HTMLSpanElement>(null)
  const [open, setOpen] = useState(false)
  const [positioned, setPositioned] = useState(false)
  const [position, setPosition] = useState<TooltipPosition>({
    left: VIEWPORT_PADDING,
    top: VIEWPORT_PADDING,
    width: TOOLTIP_WIDTH,
  })

  const updatePosition = useCallback(() => {
    const trigger = triggerRef.current
    const tooltip = tooltipRef.current
    if (!trigger || !tooltip) return

    const triggerRect = trigger.getBoundingClientRect()
    const width = Math.min(
      TOOLTIP_WIDTH,
      Math.max(0, window.innerWidth - VIEWPORT_PADDING * 2),
    )
    const tooltipHeight = tooltip.getBoundingClientRect().height
    const preferredLeft = align === 'end'
      ? triggerRect.right - width
      : triggerRect.left
    const maxLeft = Math.max(
      VIEWPORT_PADDING,
      window.innerWidth - width - VIEWPORT_PADDING,
    )
    const left = Math.min(
      Math.max(preferredLeft, VIEWPORT_PADDING),
      maxLeft,
    )

    const aboveTop = triggerRect.top - tooltipHeight - TOOLTIP_GAP
    const belowTop = triggerRect.bottom + TOOLTIP_GAP
    let top = side === 'above' ? aboveTop : belowTop
    if (top < VIEWPORT_PADDING) top = belowTop
    if (top + tooltipHeight > window.innerHeight - VIEWPORT_PADDING) {
      top = aboveTop
    }
    top = Math.min(
      Math.max(top, VIEWPORT_PADDING),
      Math.max(VIEWPORT_PADDING, window.innerHeight - tooltipHeight - VIEWPORT_PADDING),
    )

    setPosition({ left, top, width })
    setPositioned(true)
  }, [align, side])

  useLayoutEffect(() => {
    if (!open) return
    updatePosition()
    window.addEventListener('resize', updatePosition)
    window.addEventListener('scroll', updatePosition, true)
    return () => {
      window.removeEventListener('resize', updatePosition)
      window.removeEventListener('scroll', updatePosition, true)
    }
  }, [open, updatePosition])

  const showTooltip = () => {
    setPositioned(false)
    setOpen(true)
  }

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={showTooltip}
      onMouseLeave={() => setOpen(false)}
    >
      <span
        ref={triggerRef}
        tabIndex={0}
        aria-describedby={descriptionId}
        onFocus={showTooltip}
        onBlur={() => setOpen(false)}
        className="cursor-help border-b border-dotted border-current/40 outline-none focus-visible:rounded focus-visible:ring-2 focus-visible:ring-blue-500"
      >
        {children}
      </span>
      <span id={descriptionId} role="tooltip" className="sr-only">
        {description}
      </span>
      {open && typeof document !== 'undefined' && createPortal(
        <span
          ref={tooltipRef}
          aria-hidden="true"
          className="pointer-events-none fixed z-[100] rounded-md border border-gray-700 bg-gray-900 px-3 py-2 text-xs leading-5 text-white shadow-lg"
          style={{
            left: position.left,
            top: position.top,
            width: position.width,
            opacity: positioned ? 1 : 0,
          }}
        >
          {description}
        </span>,
        document.body,
      )}
    </span>
  )
}
