"use client";

import { useEffect, useState } from "react";
import { Inbox, RefreshCw } from "lucide-react";
import { useUserId } from "../providers";
import {
  fetchEmails,
  listEmails,
  processStoredPipeline,
} from "../lib/api";

function formatShortTime(iso: string | undefined): string {
  if (!iso) return "";
  try {
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const hours = Math.floor(diffMs / (1000 * 60 * 60));
    if (hours < 48) return `${hours || 1}h ago`;
    const days = Math.floor(hours / 24);
    return `${days}d ago`;
  } catch {
    return "";
  }
}

export default function InboxPage() {
  const { userId } = useUserId();
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [provider, setProvider] = useState("gmail");

  const load = () => {
    setLoading(true);
    setError(null);
    listEmails(userId, 1, 100)
      .then(res => setItems(res.items || []))
      .catch(e =>
        setError(e instanceof Error ? e.message : "Failed to load inbox"),
      )
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [userId]);

  async function handleSync() {
    setSyncing(true);
    setNotice(null);
    setError(null);
    try {
      await fetchEmails(userId, provider, 50);
      setNotice(
        "Fetch queued on the worker. After it completes, refresh or run pipeline.",
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function handlePipeline() {
    setSyncing(true);
    setNotice(null);
    setError(null);
    try {
      const r = await processStoredPipeline(userId, 30);
      setNotice(
        `Pipeline: ${r.drafts_created} drafts created, ${r.skipped} skipped, ${r.pipeline_errors} errors.`,
      );
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Pipeline failed");
    } finally {
      setSyncing(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h2>Inbox Triage</h2>
        <p>Emails from the API for the current User ID</p>
      </div>

      {(error || notice) && (
        <div
          className="card"
          style={{
            marginBottom: "1rem",
            fontSize: "0.875rem",
            borderColor: error ? "var(--danger)" : "var(--border)",
            color: error ? "var(--danger)" : "var(--text-secondary)",
          }}
        >
          {error || notice}
        </div>
      )}

      <div
        style={{
          display: "flex",
          gap: "0.5rem",
          marginBottom: "1.5rem",
          flexWrap: "wrap",
          alignItems: "center",
        }}
      >
        <select
          value={provider}
          onChange={e => setProvider(e.target.value)}
          className="btn btn-ghost"
          style={{
            padding: "0.5rem 0.75rem",
            border: "1px solid var(--border)",
            borderRadius: "var(--radius-sm)",
            background: "var(--bg-secondary)",
            color: "var(--text-primary)",
          }}
        >
          <option value="gmail">Gmail</option>
          <option value="outlook">Outlook</option>
        </select>
        <button
          className="btn btn-primary"
          disabled={syncing}
          onClick={handleSync}
        >
          <RefreshCw size={14} /> Queue fetch
        </button>
        <button
          className="btn btn-ghost"
          disabled={syncing}
          onClick={handlePipeline}
          title="Run LangGraph pipeline on stored emails"
        >
          Run AI pipeline
        </button>
        <button className="btn btn-ghost" disabled={loading} onClick={load}>
          Refresh list
        </button>
      </div>

      <div className="card" style={{ padding: 0 }}>
        {loading && (
          <div style={{ padding: "2rem", color: "var(--text-muted)" }}>
            Loading…
          </div>
        )}
        {!loading &&
          items.map((email: any) => (
            <div key={email.message_id} className="email-item">
              <div style={{ flex: 1, minWidth: 0 }}>
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "0.25rem",
                  }}
                >
                  <span className="email-sender">{email.sender || "—"}</span>
                  <span className="email-time">
                    {formatShortTime(email.timestamp)}
                  </span>
                </div>
                <div className="email-subject">{email.subject || "(no subject)"}</div>
                <div className="email-preview">
                  {(email.body_clean || "").slice(0, 160)}
                  {(email.body_clean || "").length > 160 ? "…" : ""}
                </div>
              </div>
              <span className="badge lead">{email.platform || "mail"}</span>
            </div>
          ))}
        {!loading && items.length === 0 && (
          <div className="empty-state">
            <Inbox size={48} />
            <p>No emails loaded for this user.</p>
          </div>
        )}
      </div>
    </>
  );
}
