"use client";

import { useEffect, useState } from "react";
import {
  Inbox,
  FileEdit,
  Users,
  Megaphone,
  TrendingUp,
  Mail,
} from "lucide-react";
import { useUserId } from "./providers";
import { getStats, listEmails } from "./lib/api";

function formatShortTime(iso: string | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    if (hours < 24) return `${hours || 1}h`;
    const days = Math.floor(hours / 24);
    return `${days}d`;
  } catch {
    return "";
  }
}

export default function DashboardPage() {
  const { userId } = useUserId();
  const [stats, setStats] = useState({
    emails: 0,
    drafts: 0,
    leads: 0,
    campaigns: 0,
  });
  const [recent, setRecent] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([
      getStats(userId),
      listEmails(userId, 1, 8),
    ])
      .then(([s, inbox]) => {
        if (cancelled) return;
        setStats({
          emails: s.emails,
          drafts: s.drafts,
          leads: s.leads,
          campaigns: s.campaigns,
        });
        setRecent(inbox.items || []);
      })
      .catch(e => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [userId]);

  const pendingDraftsApprox = stats.drafts;

  return (
    <>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Overview of your Nexus Mail Agent activity</p>
      </div>

      {error && (
        <div
          className="card"
          style={{
            marginBottom: "1rem",
            borderColor: "var(--danger)",
            color: "var(--danger)",
            fontSize: "0.875rem",
          }}
        >
          {error} — ensure the API is running and{" "}
          <code style={{ fontSize: "0.8em" }}>User ID</code> matches your data.
        </div>
      )}

      {/* Stats Row */}
      <div className="grid-4" style={{ marginBottom: "2rem" }}>
        <div className="stat-card">
          <div className="stat-icon purple">
            <Mail size={22} />
          </div>
          <div>
            <div className="stat-value">{loading ? "—" : stats.emails}</div>
            <div className="stat-label">Emails stored</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon green">
            <FileEdit size={22} />
          </div>
          <div>
            <div className="stat-value">{loading ? "—" : stats.drafts}</div>
            <div className="stat-label">Drafts</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon amber">
            <Users size={22} />
          </div>
          <div>
            <div className="stat-value">{loading ? "—" : stats.leads}</div>
            <div className="stat-label">Leads</div>
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-icon blue">
            <Megaphone size={22} />
          </div>
          <div>
            <div className="stat-value">{loading ? "—" : stats.campaigns}</div>
            <div className="stat-label">Campaigns</div>
          </div>
        </div>
      </div>

      {/* Recent Activity */}
      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Recent Inbox</h3>
            {!loading && recent.length > 0 && (
              <span className="badge lead">{recent.length} shown</span>
            )}
          </div>
          <div className="stack">
            {loading && (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                Loading…
              </p>
            )}
            {!loading &&
              recent.map((e: any) => (
                <div
                  key={e.message_id || e.id}
                  className="email-item"
                  style={{ border: "none", padding: "0.75rem 0" }}
                >
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                      }}
                    >
                      <span className="email-sender">{e.sender || "—"}</span>
                      <span className="email-time">
                        {formatShortTime(e.timestamp)}
                      </span>
                    </div>
                    <div className="email-subject">{e.subject || "(no subject)"}</div>
                  </div>
                </div>
              ))}
            {!loading && recent.length === 0 && (
              <p style={{ color: "var(--text-muted)", fontSize: "0.875rem" }}>
                No emails yet. Use Inbox → Sync to fetch mail.
              </p>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-header">
            <h3 className="card-title">Pipeline snapshot</h3>
            <TrendingUp size={18} style={{ color: "var(--success)" }} />
          </div>
          <div className="stack">
            <p style={{ fontSize: "0.8125rem", color: "var(--text-secondary)" }}>
              Stored emails: <strong>{loading ? "—" : stats.emails}</strong>
              <br />
              Drafts awaiting review: <strong>{loading ? "—" : pendingDraftsApprox}</strong>
              <br />
              Campaigns: <strong>{loading ? "—" : stats.campaigns}</strong>
            </p>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
              Detailed analyst/copywriter/critic scores live on each draft record (
              <code>agent_result</code>).
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
