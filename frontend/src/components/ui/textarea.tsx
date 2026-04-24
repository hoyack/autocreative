// ShadCN-style Textarea primitive — editorial treatment matches Input.
import * as React from "react";

import { cn } from "@/lib/utils";

function Textarea({
  className,
  ...props
}: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "field-sizing-content flex min-h-[80px] w-full rounded-none border-0 border-b border-border bg-transparent px-0 py-2 text-base text-foreground transition-colors outline-none",
        "placeholder:font-display placeholder:italic placeholder:text-muted-foreground/70",
        "focus-visible:border-b-2 focus-visible:border-amber",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive",
        className,
      )}
      {...props}
    />
  );
}

export { Textarea };
