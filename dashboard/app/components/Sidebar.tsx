"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUserId } from "../providers";
import {
  Inbox,
  FileEdit,
  Users,
  Megaphone,
  LayoutDashboard,
  Settings,
} from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/inbox", label: "Inbox Triage", icon: Inbox },
  { href: "/drafts", label: "Draft Review", icon: FileEdit },
  { href: "/leads", label: "Lead Cards", icon: Users },
  { href: "/campaigns", label: "Campaigns", icon: Megaphone },
];

export function Sidebar() {
  const pathname = usePathname();
  const { userId, setUserId } = useUserId();

  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <h1>Nexus Mail</h1>
        <span>AI Outreach Agent</span>
      </div>

      <div style={{ padding: "0 1rem 1rem", fontSize: "0.75rem" }}>
        <label style={{ display: "block", color: "var(--text-muted)", marginBottom: "0.375rem" }}>
          User ID
        </label>
        <input
          className="btn btn-ghost"
          style={{
            width: "100%",
            padding: "0.5rem 0.625rem",
            fontSize: "0.8125rem",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
          }}
          value={userId}
          onChange={e => setUserId(e.target.value)}
          placeholder="demo-user"
          title="Matches Supabase user_id / OAuth subject"
        />
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={`nav-link ${pathname === href ? "active" : ""}`}
          >
            <Icon />
            {label}
          </Link>
        ))}
      </nav>

      <div className="sidebar-nav" style={{ marginTop: "auto" }}>
        <Link href="/settings" className="nav-link">
          <Settings />
          Settings
        </Link>
      </div>
    </aside>
  );
}
