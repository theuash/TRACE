import {
  LayoutDashboard,
  FilePlus2,
  ListChecks,
  FolderOpen,
  Gauge,
  ScrollText,
  Settings,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
}

/** The navigation, shared by the sidebar and the phone drawer. */
export const NAV_ITEMS: NavItem[] = [
  { to: "/overview", label: "Overview", icon: LayoutDashboard },
  { to: "/new", label: "New audit", icon: FilePlus2 },
  { to: "/review", label: "Review queue", icon: ListChecks },
  { to: "/filings", label: "Filings", icon: FolderOpen },
  { to: "/accuracy", label: "Accuracy", icon: Gauge },
  { to: "/audit", label: "Audit log", icon: ScrollText },
  { to: "/settings", label: "Settings", icon: Settings },
];
