import { useRef, useState, type DragEvent, type InputHTMLAttributes, type ReactNode } from 'react'
import { cn } from '@/lib/cn'

export interface DropZoneRenderState {
  dragging: boolean
  /** Opens the native file picker. */
  browse: () => void
}

export interface DropZoneProps {
  onFiles: (files: File[]) => void
  accept?: string
  multiple?: boolean
  /** Pick a whole folder (webkitdirectory). Dropping folders is not supported, browsing is. */
  directory?: boolean
  disabled?: boolean
  /** Accessible name of the hidden file input. */
  inputLabel: string
  className?: string
  children: (state: DropZoneRenderState) => ReactNode
}

/**
 * Drag & drop surface with a hidden file input. The visible content must include a real
 * button calling `browse` so keyboard users can pick a file too.
 */
export function DropZone({
  onFiles,
  accept,
  multiple = false,
  directory = false,
  disabled = false,
  inputLabel,
  className,
  children,
}: DropZoneProps) {
  const inputRef = useRef<HTMLInputElement>(null)
  const depth = useRef(0)
  const [dragging, setDragging] = useState(false)

  const browse = () => {
    if (!disabled) inputRef.current?.click()
  }

  const accepts = (e: DragEvent) => !disabled && Array.from(e.dataTransfer.types).includes('Files')

  const onDragEnter = (e: DragEvent) => {
    if (!accepts(e)) return
    e.preventDefault()
    depth.current += 1
    setDragging(true)
  }
  const onDragOver = (e: DragEvent) => {
    if (!accepts(e)) return
    e.preventDefault()
    e.dataTransfer.dropEffect = 'copy'
  }
  const onDragLeave = (e: DragEvent) => {
    if (!accepts(e)) return
    depth.current = Math.max(0, depth.current - 1)
    if (depth.current === 0) setDragging(false)
  }
  const onDrop = (e: DragEvent) => {
    if (disabled) return
    e.preventDefault()
    depth.current = 0
    setDragging(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) onFiles(multiple ? files : files.slice(0, 1))
  }

  const directoryProps = (directory ? { webkitdirectory: '', directory: '' } : {}) as InputHTMLAttributes<HTMLInputElement>

  return (
    <div
      onDragEnter={onDragEnter}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      data-dragging={dragging || undefined}
      className={cn('relative', className)}
    >
      {children({ dragging, browse })}
      <input
        ref={inputRef}
        type="file"
        className="sr-only"
        tabIndex={-1}
        aria-label={inputLabel}
        accept={accept}
        multiple={multiple || directory}
        disabled={disabled}
        onChange={(e) => {
          const files = Array.from(e.target.files ?? [])
          e.target.value = ''
          if (files.length) onFiles(files)
        }}
        {...directoryProps}
      />
    </div>
  )
}
