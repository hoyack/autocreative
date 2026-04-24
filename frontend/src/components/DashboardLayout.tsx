import { Link, NavLink, Outlet } from "react-router";

const NAV = [
  { to: "/brand-kits", label: "Brand kits" },
  { to: "/flyers/new", label: "New flyer" },
  { to: "/brochures/new", label: "New brochure" },
  { to: "/social/posts/new", label: "New post" },
  { to: "/social/campaigns/new", label: "New campaign" },
  { to: "/jobs", label: "Jobs" },
  { to: "/renders", label: "Renders" },
] as const;

export function DashboardLayout() {
  return (
    <div className="relative z-0 flex min-h-svh bg-background">
      <aside className="sticky top-0 flex h-svh w-[260px] shrink-0 flex-col justify-between bg-sidebar px-7 pt-8 pb-6 text-sidebar-foreground">
        <div>
          <Link to="/" className="block group">
            <div className="flex items-baseline gap-1 leading-none">
              <span
                className="font-display text-3xl font-light italic tracking-tight text-sidebar-foreground transition-colors group-hover:text-amber"
                style={{
                  fontVariationSettings: '"opsz" 144, "SOFT" 60, "WONK" 1',
                }}
              >
                flyer
              </span>
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber"
                aria-hidden
              />
            </div>
            <div className="mt-0.5 font-mono text-[10px] tracking-[0.24em] uppercase text-sidebar-foreground/55">
              generator · v1
            </div>
          </Link>

          <div className="mt-11 mb-4 font-mono text-[10px] tracking-[0.26em] uppercase text-sidebar-foreground/45">
            Index
          </div>

          <nav aria-label="Primary">
            <ol className="space-y-0">
              {NAV.map((item, i) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    end={false}
                    className={({ isActive }) =>
                      [
                        "group relative flex items-baseline gap-3.5 py-2 text-[15px] leading-6 transition-colors",
                        isActive
                          ? "text-sidebar-foreground"
                          : "text-sidebar-foreground/65 hover:text-sidebar-foreground",
                      ].join(" ")
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <span
                          className={[
                            "font-mono text-[10px] tabular-nums tracking-widest transition-colors",
                            isActive
                              ? "text-amber"
                              : "text-sidebar-foreground/35 group-hover:text-sidebar-foreground/55",
                          ].join(" ")}
                          aria-hidden
                        >
                          {String(i + 1).padStart(2, "0")}
                        </span>
                        <span className="flex-1">{item.label}</span>
                        {isActive && (
                          <span
                            className="absolute left-0 top-1/2 h-px w-5 -translate-x-[calc(100%+0.5rem)] -translate-y-1/2 bg-amber"
                            aria-hidden
                          />
                        )}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ol>
          </nav>
        </div>

        <div className="border-t border-sidebar-border pt-4 font-mono text-[10px] leading-[1.6] tracking-[0.08em] uppercase text-sidebar-foreground/40">
          <div>Set in Fraunces &amp; Geist</div>
          <div>No. 21 · {new Date().getFullYear()}</div>
        </div>
      </aside>

      <main className="relative flex-1">
        <Outlet />
      </main>
    </div>
  );
}
