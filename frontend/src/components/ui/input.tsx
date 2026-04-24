import * as React from "react";

import { cn } from "@/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        // Editorial treatment: no rounded corners, no border — just a
        // bottom hairline that thickens + goes amber on focus. Font swaps
        // to Fraunces italic at rest so placeholders feel typographic.
        "h-11 w-full min-w-0 rounded-none border-0 border-b border-border bg-transparent px-0 py-2 text-base text-foreground transition-colors outline-none",
        "placeholder:font-display placeholder:italic placeholder:text-muted-foreground/70",
        "focus-visible:border-b-2 focus-visible:border-amber",
        "disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
        "aria-invalid:border-destructive",
        "file:inline-flex file:h-8 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        className,
      )}
      {...props}
    />
  );
}

export { Input };
