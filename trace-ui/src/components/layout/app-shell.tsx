import { Outlet, useLocation } from "react-router-dom";
import { Sidebar } from "./sidebar";
import { Topbar } from "./topbar";

const titles: Record<string, string> = {
  "/": "Overview",
  "/new": "New audit",
  "/review": "Review queue",
  "/filings": "Filings",
  "/accuracy": "Accuracy",
  "/audit": "Audit log",
  "/settings": "Settings",
};

export function AppShell() {
  const location = useLocation();
  const pageTitle = titles[location.pathname] ?? "TRACE";

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <Sidebar />
      <div className="flex min-h-screen flex-1 flex-col md:pl-64">
        <Topbar />
        <main id="main-content" className="flex-1 px-6 py-8">
          <div className="mb-6">
            <h1 className="font-sans text-2xl font-semibold tracking-tight text-foreground">{pageTitle}</h1>
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
