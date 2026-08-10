export async function copyText(value: string): Promise<boolean> {
  if (!value) return false

  if (
    typeof window !== 'undefined'
    && typeof navigator !== 'undefined'
    && window.isSecureContext
    && navigator.clipboard?.writeText
  ) {
    try {
      await navigator.clipboard.writeText(value)
      return true
    } catch {
      // Continue with the selection-based fallback below.
    }
  }

  if (typeof document === 'undefined' || !document.body) return false

  const textarea = document.createElement('textarea')
  const activeElement = document.activeElement instanceof HTMLElement
    ? document.activeElement
    : null

  textarea.value = value
  textarea.readOnly = true
  textarea.setAttribute('aria-hidden', 'true')
  textarea.style.position = 'fixed'
  textarea.style.left = '-9999px'
  textarea.style.top = '0'
  textarea.style.opacity = '0'
  textarea.style.pointerEvents = 'none'
  document.body.appendChild(textarea)

  let copied = false
  try {
    textarea.focus({ preventScroll: true })
    textarea.select()
    textarea.setSelectionRange(0, textarea.value.length)
    copied = document.execCommand('copy')
  } catch {
    copied = false
  } finally {
    textarea.remove()
    try {
      activeElement?.focus({ preventScroll: true })
    } catch {
      // Copy result should not change if the previous element cannot regain focus.
    }
  }

  return copied
}

export function copyStatus(copied: boolean, successMessage: string): string {
  return copied
    ? successMessage
    : '浏览器未允许自动复制，请选中上方内容后按 Ctrl+C（macOS 按 Cmd+C）。'
}
