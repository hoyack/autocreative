import type { ReactNode } from "react";

interface PageHeaderProps {
  kicker?: string;
  number?: string;
  title: string;
  dek?: string;
  actions?: ReactNode;
}

export function PageHeader({
  kicker,
  number,
  title,
  dek,
  actions,
}: PageHeaderProps) {
  return (
    <header className="border-b border-border pb-10 mb-10">
      {(kicker || number) && (
        <div className="flex items-baseline gap-4 mb-6 font-mono text-[11px] tracking-[0.2em] uppercase text-muted-foreground">
          {number && (
            <span className="text-amber tabular-nums">{number}</span>
          )}
          {number && kicker && <span aria-hidden>/</span>}
          {kicker && <span>{kicker}</span>}
        </div>
      )}
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="min-w-0">
          <h1
            className="text-6xl font-normal leading-[0.95] tracking-[-0.025em] text-foreground"
            style={{
              fontVariationSettings:
                '"opsz" 144, "SOFT" 40, "WONK" 0',
            }}
          >
            {title}
          </h1>
          {dek && (
            <p
              className="mt-5 max-w-[54ch] font-display text-lg italic leading-snug text-muted-foreground"
              style={{
                fontVariationSettings:
                  '"opsz" 14, "SOFT" 60, "WONK" 1',
              }}
            >
              {dek}
            </p>
          )}
        </div>
        {actions && (
          <div className="flex shrink-0 items-center gap-2">{actions}</div>
        )}
      </div>
    </header>
  );
}
