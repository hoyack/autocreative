import * as React from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { Slot } from "radix-ui";

import { cn } from "@/lib/utils";

const buttonVariants = cva(
  // Base: flat rectangle, letterspaced mono type, no rounded corners.
  "group/button inline-flex shrink-0 items-center justify-center rounded-none border border-transparent font-mono text-[11px] font-medium uppercase tracking-[0.16em] whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-2 focus-visible:ring-amber/40 focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default:
          "bg-foreground text-background hover:bg-amber hover:text-background",
        outline:
          "border border-foreground bg-transparent text-foreground hover:border-amber hover:text-amber",
        secondary:
          "border border-border bg-card text-foreground hover:border-amber hover:text-amber",
        ghost:
          "bg-transparent text-foreground hover:text-amber",
        destructive:
          "bg-destructive text-background hover:bg-destructive/85",
        link:
          "h-auto px-0 py-0 text-foreground normal-case tracking-normal font-sans underline decoration-amber decoration-2 underline-offset-4 hover:text-amber",
      },
      size: {
        default: "h-10 px-5 py-2 gap-2",
        xs: "h-7 px-2.5 text-[10px] gap-1.5",
        sm: "h-8 px-3.5 text-[10px] gap-1.5",
        lg: "h-11 px-6 gap-2",
        icon: "size-10",
        "icon-xs": "size-7 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8 [&_svg:not([class*='size-'])]:size-3.5",
        "icon-lg": "size-11",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  },
);

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean;
  }) {
  const Comp = asChild ? Slot.Root : "button";

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  );
}

export { Button, buttonVariants };
