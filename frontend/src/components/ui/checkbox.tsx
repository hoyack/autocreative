// ShadCN-style Checkbox primitive (radix-nova).
//
// Added in plan 21-09 for the social campaign creator form (multi-platform
// picker). Wraps @radix-ui/react-checkbox via the `radix-ui` meta-package
// entry-point used elsewhere in the primitive set (see label.tsx which
// imports `Label as LabelPrimitive` from "radix-ui").
//
// The token chain mirrors the Input / Textarea primitives so focus-visible,
// aria-invalid, and disabled states read consistently across form inputs.
// The indicator centers a lucide Check icon when the checkbox is checked.
//
// We intentionally do NOT run `npx shadcn@latest add checkbox` — per plan
// 21-05 / 21-08 decisions, the radix-nova ShadCN registry has been known
// to return empty stubs. Hand-writing the primitive mirrors the working
// Label primitive's idiom and avoids that risk.
import * as React from "react"
import { Checkbox as CheckboxPrimitive } from "radix-ui"
import { Check } from "lucide-react"

import { cn } from "@/lib/utils"

function Checkbox({
  className,
  ...props
}: React.ComponentProps<typeof CheckboxPrimitive.Root>) {
  return (
    <CheckboxPrimitive.Root
      data-slot="checkbox"
      className={cn(
        "peer size-4 shrink-0 rounded-sm border border-input bg-transparent shadow-sm transition-colors outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=checked]:text-primary-foreground data-[state=checked]:border-primary aria-invalid:border-destructive aria-invalid:ring-3 aria-invalid:ring-destructive/20",
        className
      )}
      {...props}
    >
      <CheckboxPrimitive.Indicator
        data-slot="checkbox-indicator"
        className={cn(
          "flex items-center justify-center text-current"
        )}
      >
        <Check className="size-3.5" />
      </CheckboxPrimitive.Indicator>
    </CheckboxPrimitive.Root>
  )
}

export { Checkbox }
