// Source: 21-RESEARCH.md Pattern 5 (verbatim, lines 924-966) with 7-entry NAV
// per 21-CONTEXT.md line 36 (Brand kits / New flyer / New brochure / New post /
// New campaign / Jobs / Renders).
import { Link, NavLink, Outlet } from "react-router";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarProvider,
} from "@/components/ui/sidebar";

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
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader>
          <Link to="/" className="font-semibold">
            flyer-generator
          </Link>
        </SidebarHeader>
        <SidebarContent>
          <SidebarMenu>
            {NAV.map((item) => (
              <SidebarMenuItem key={item.to}>
                <NavLink to={item.to}>
                  {({ isActive }) => (
                    <SidebarMenuButton isActive={isActive}>
                      {item.label}
                    </SidebarMenuButton>
                  )}
                </NavLink>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarContent>
      </Sidebar>
      <main className="flex-1 p-6">
        <Outlet />
      </main>
    </SidebarProvider>
  );
}
