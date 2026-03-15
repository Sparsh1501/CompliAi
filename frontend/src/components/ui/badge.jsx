import * as React from "react"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-lg border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:ring-offset-2 focus:ring-offset-white",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-[#059669] text-white shadow hover:bg-[#047857]",
        secondary:
          "border-[#E5E7EB] bg-[#F9FAFB] text-[#6B7280] hover:bg-[#F3F4F6]",
        destructive:
          "border-transparent bg-[#EF4444] text-white shadow hover:bg-[#EF4444]/80",
        outline: "border-[#E5E7EB] text-[#6B7280] bg-transparent",
        success:
          "border-transparent bg-[#10B981] text-white shadow hover:bg-[#10B981]/80",
        warning:
          "border-transparent bg-[#F59E0B] text-white shadow hover:bg-[#F59E0B]/80",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant,
  ...props
}) {
  return (<div className={cn(badgeVariants({ variant }), className)} {...props} />);
}

export { Badge, badgeVariants }
