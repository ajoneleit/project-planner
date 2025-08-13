'use client'

import { useState, useRef, useEffect, forwardRef } from 'react'
import { cn } from '@/lib/utils'

interface ExpandableTextareaProps {
  value: string
  onChange: (e: React.ChangeEvent<HTMLTextAreaElement>) => void
  onKeyPress?: (e: React.KeyboardEvent<HTMLTextAreaElement>) => void
  placeholder?: string
  disabled?: boolean
  className?: string
  maxRows?: number
  minRows?: number
}

export const ExpandableTextarea = forwardRef<HTMLTextAreaElement, ExpandableTextareaProps>(
  ({ 
    value, 
    onChange, 
    onKeyPress, 
    placeholder, 
    disabled, 
    className, 
    maxRows = 5, 
    minRows = 1 
  }, ref) => {
    const [height, setHeight] = useState('auto')
    const textareaRef = useRef<HTMLTextAreaElement>(null)
    const hiddenTextareaRef = useRef<HTMLTextAreaElement>(null)

    // Update height when content changes
    useEffect(() => {
      const textarea = textareaRef.current
      const hiddenTextarea = hiddenTextareaRef.current
      
      if (!textarea || !hiddenTextarea) return

      // Copy styles to hidden textarea for accurate measurement
      const computedStyle = window.getComputedStyle(textarea)
      hiddenTextarea.style.font = computedStyle.font
      hiddenTextarea.style.fontSize = computedStyle.fontSize
      hiddenTextarea.style.fontFamily = computedStyle.fontFamily
      hiddenTextarea.style.fontWeight = computedStyle.fontWeight
      hiddenTextarea.style.lineHeight = computedStyle.lineHeight
      hiddenTextarea.style.letterSpacing = computedStyle.letterSpacing
      hiddenTextarea.style.padding = computedStyle.padding
      hiddenTextarea.style.border = computedStyle.border
      hiddenTextarea.style.boxSizing = computedStyle.boxSizing
      hiddenTextarea.style.width = computedStyle.width

      // Set content and measure
      hiddenTextarea.value = value || placeholder || ''
      const scrollHeight = hiddenTextarea.scrollHeight

      // Calculate line height
      const lineHeight = parseInt(computedStyle.lineHeight) || 24
      const paddingTop = parseInt(computedStyle.paddingTop) || 0
      const paddingBottom = parseInt(computedStyle.paddingBottom) || 0
      const borderTop = parseInt(computedStyle.borderTopWidth) || 0
      const borderBottom = parseInt(computedStyle.borderBottomWidth) || 0

      const contentHeight = scrollHeight - paddingTop - paddingBottom - borderTop - borderBottom
      const lines = Math.max(minRows, Math.min(maxRows, Math.ceil(contentHeight / lineHeight)))
      const newHeight = lines * lineHeight + paddingTop + paddingBottom + borderTop + borderBottom

      setHeight(`${newHeight}px`)
    }, [value, maxRows, minRows, placeholder])

    const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      onChange(e)
    }

    const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (onKeyPress) {
        onKeyPress(e)
      }
    }

    return (
      <div className="relative">
        <textarea
          ref={(element) => {
            textareaRef.current = element
            if (typeof ref === 'function') {
              ref(element)
            } else if (ref) {
              ref.current = element
            }
          }}
          value={value}
          onChange={handleChange}
          onKeyPress={handleKeyPress}
          placeholder={placeholder}
          disabled={disabled}
          style={{ height }}
          className={cn(
            "expandable-textarea min-h-[40px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background",
            "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            "disabled:cursor-not-allowed disabled:opacity-50",
            className
          )}
        />
        
        {/* Hidden textarea for measurement */}
        <textarea
          ref={hiddenTextareaRef}
          tabIndex={-1}
          className="absolute left-0 top-0 -z-10 opacity-0 pointer-events-none overflow-hidden whitespace-pre-wrap"
          style={{
            height: 'auto',
            minHeight: 'auto',
            maxHeight: 'none',
            resize: 'none'
          }}
          aria-hidden="true"
        />
      </div>
    )
  }
)

ExpandableTextarea.displayName = 'ExpandableTextarea'