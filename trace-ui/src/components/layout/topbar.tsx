import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Menu, Plus, Search, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { NAV_ITEMS } from "@/components/layout/nav-items";
import { useThreads } from "@/hooks/use-trace";
import { pendingItemCount } from "@/lib/threads";
import { cn } from "@/lib/utils";

export function Topbar() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [menuOpen, setMenuOpen] = useState(false);
  const { data: threads } = useThreads();
  const pending = pendingItemCount(threads);

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    const q = query.trim();
    if (q) navigate(`/filings?search=${encodeURIComponent(q)}`);
  };

  const go = (to: string) => {
    setMenuOpen(false);
    navigate(to);
  };

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b bg-background/90 px-4 backdrop-blur md:px-6">
      {/* The sidebar is hidden on small screens, so the phone needs its own way in. */}
      <Button
        variant="ghost"
        size="sm"
        className="md:hidden"
        onClick={() => setMenuOpen(true)}
        aria-label="Open the navigation"
        data-testid="menu-button"
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
      </Button>

      <form onSubmit={onSearch} className="relative w-full max-w-sm" role="search">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search company, ticker, CIK"
          className="pl-8"
          aria-label="Search companies, tickers, or CIKs"
        />
      </form>
      <div className="ml-auto flex items-center gap-2">
        <Button size="sm" onClick={() => navigate("/new")}>
          <Plus className="h-4 w-4" aria-hidden="true" />
          <span className="hidden sm:inline">New audit</span>
        </Button>
      </div>

      {menuOpen ? (
        <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <button
            type="button"
            aria-label="Close the navigation"
            className="absolute inset-0 bg-foreground/30"
            onClick={() => setMenuOpen(false)}
          />
          <nav className="absolute inset-y-0 left-0 flex w-72 flex-col border-r bg-card p-4 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <span className="text-lg font-semibold tracking-[0.2em]">TRACE</span>
              <Button variant="ghost" size="sm" onClick={() => setMenuOpen(false)} aria-label="Close the navigation">
                <X className="h-5 w-5" aria-hidden="true" />
              </Button>
            </div>
            <div className="flex flex-1 flex-col gap-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                return (
                  <button
                    key={item.to}
                    type="button"
                    onClick={() => go(item.to)}
                    className={cn(
                      "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                      "text-muted-foreground hover:bg-accent hover:text-foreground"
                    )}
                    data-testid={`mobile-nav-${item.to.replace(/\//g, "")}`}
                  >
                    <Icon className="h-4 w-4" aria-hidden="true" />
                    <span className="flex-1 text-left">{item.label}</span>
                    {item.to === "/review" && pending > 0 ? (
                      <span className="rounded-full bg-warning/15 px-2 py-0.5 text-xs font-semibold text-warning">
                        {pending}
                      </span>
                    ) : null}
                  </button>
                );
              })}
            </div>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
