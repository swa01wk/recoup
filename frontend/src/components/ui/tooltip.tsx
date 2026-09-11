"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface TooltipProps {
  content: React.ReactNode
  children: React.ReactNode
  className?: string
}

function Tooltip({ content, children, className }: TooltipProps) {
  const [show, setShow] = React.useState(false)

  return (
    <span
      className="relative inline-flex"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      {children}
      {show && (
        <span
          className={cn(
            "absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-max max-w-xs rounded-md border border-slate-600 bg-slate-800 px-2.5 py-1.5 text-xs text-slate-200 shadow-lg",
            className
          )}
        >
          {content}
        </span>
      )}
    </span>
  )
}

export { Tooltip }
