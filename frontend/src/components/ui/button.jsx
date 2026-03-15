import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default:
          "bg-gradient-to-r from-[#059669] to-[#047857] text-white shadow-lg hover:shadow-[0_0_20px_rgba(5,150,105,0.3)] hover:scale-[1.02]",
        destructive:
          "bg-[#EF4444] text-white shadow-sm hover:bg-[#EF4444]/90",
        outline:
          "border border-[#E5E7EB] bg-transparent text-[#111827] shadow-sm hover:bg-[#F3F4F6] hover:border-[#059669]/50",
        secondary:
          "bg-[#F9FAFB] text-[#111827] border border-[#E5E7EB] shadow-sm hover:bg-[#F3F4F6]",
        ghost: "text-[#6B7280] hover:bg-[#F3F4F6] hover:text-[#111827]",
        link: "text-[#059669] underline-offset-4 hover:underline",
        teal: "bg-[#059669] text-white shadow-lg hover:shadow-[0_0_20px_rgba(5,150,105,0.3)] hover:scale-[1.02]",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md px-3 text-xs",
        lg: "h-10 rounded-lg px-8",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
