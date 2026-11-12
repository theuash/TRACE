import { LayoutDashboard, FilePlus2, ListChecks, FolderOpen, Gauge, ScrollText, Settings } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useThreads, useDataMode } from "@/hooks/use-trace";
import { useTheme } from "@/components/theme-provider";
import { cn } from "@/lib/utils";

const navItems = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/new", label: "New audit", icon: FilePlus2 },
  { to: "/review", label: "Review queue", icon: ListChecks },
  { to: "/filings", icon: FolderOpen, label: "Filings" },
  { to: "/accuracy", label: "Accuracy", icon: Gauge },
  { to: "/audit", label: "Audit log", icon: ScrollText },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const location = useLocation();
  const { mode } = useDataMode();
  const { theme, toggleTheme } = useTheme();
  const { data: threads } = useThreads();

  const pendingCount = (threads ?? []).filter(
    (t) => t.status === "PAUSED_FOR_REVIEW" || t.status === "HUMAN_REVIEWED"
  ).length;

  return (
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r bg-card md:flex">
      <div className="flex h-16 items-center gap-2.5 border-b px-5">
        <svg width="26" height="26" viewBox="0 0 32 32" fill="none" stroke="hsl(243.2 47.2% 40.4%)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M3 16h5l3-9 4 18 3-9h5" />
        </svg>
        <span className="text-lg font-semibold tracking-[0.2em] text-foreground">TRACE</span>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-4" aria-label="Primary">
        {navItems.map((item) => {
          const Icon = item.icon;
          const active = location.pathname === item.to;
          return (
            <NavLink
              key={item.to}
              to={item.to}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active ? "bg-accent text-accent-foreground" : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" aria-hidden="true" />
              <span className="flex-1">{item.label}</span>
              {item.to === "/review" && pendingCount > 0 && (
                <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-semibold text-warning" data-testid="pending-badge">
                  {pendingCount}
                </span>
              )}
            </NavLink>
          );
        })}
      </nav>
      <div className="border-t p-4">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Data mode</span>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-xs font-semibold",
              mode === "mock" ? "bg-warning/15 text-warning" : "bg-success/15 text-success"
            )}
            data-testid="data-mode"
          >
            {mode === "mock" ? "Demo data" : "Live"}
          </span>
        </div>
        <button
          type="button"
          onClick={toggleTheme}
          className="mt-3 flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
          aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"}
        >
          <span>Theme</span>
          <span className="font-medium text-foreground">{theme === "dark" ? "Dark" : "Light"}</span>
        </button>
      </div>
    </aside>
  );
}
