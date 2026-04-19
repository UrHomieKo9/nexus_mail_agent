"use client";

import { useEffect, useState } from "react";
import { Play, Pause, Plus, Users, Send, Eye } from "lucide-react";
import { useUserId } from "../providers";
import {
  createCampaign,
  listCampaigns,
  pauseCampaign,
  startCampaign,
} from "../lib/api";

function statusConfig(status: string) {
  switch (status) {
    case "active":
      return { label: "Active", className: "active" };
    case "paused":
      return { label: "Paused", className: "paused" };
    case "completed":
      return { label: "Completed", className: "sent" };
    default:
      return { label: "Draft", className: "draft" };
  }
}

function recipientCount(recipients: unknown): number {
  if (Array.isArray(recipients)) return recipients.length;
  return 0;
}

export default function CampaignsPage() {
  const { userId } = useUserId();
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [formName, setFormName] = useState("");
  const [formSubject, setFormSubject] = useState("Hi {{name}}");
  const [formBody, setFormBody] = useState("Quick note for {{company}}…");
  const [formRecipients, setFormRecipients] = useState("a@example.com");

  const load = () => {
    setLoading(true);
    setError(null);
    listCampaigns(userId)
      .then(res => setCampaigns(res.campaigns || []))
      .catch(e =>
        setError(e instanceof Error ? e.message : "Failed to load campaigns"),
      )
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [userId]);

  async function handleStart(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await startCampaign(id, true);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Start failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handlePause(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await pauseCampaign(id);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Pause failed");
    } finally {
      setBusyId(null);
    }
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const emails = formRecipients
      .split(/[\n,;]+/)
      .map(s => s.trim())
      .filter(Boolean);
    if (!formName.trim() || emails.length === 0) return;
    setBusyId("new");
    setError(null);
    try {
      await createCampaign({
        user_id: userId,
        name: formName.trim(),
        subject_template: formSubject,
        body_template: formBody,
        recipient_emails: emails,
      });
      setShowForm(false);
      setFormName("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <div
        className="page-header"
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
        }}
      >
        <div>
          <h2>Campaigns</h2>
          <p>Outreach campaigns for the current User ID</p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowForm(s => !s)}
        >
          <Plus size={14} /> New campaign
        </button>
      </div>

      {error && (
        <div
          className="card"
          style={{
            marginBottom: "1rem",
            color: "var(--danger)",
            fontSize: "0.875rem",
          }}
        >
          {error}
        </div>
      )}

      {showForm && (
        <form className="card" onSubmit={handleCreate} style={{ marginBottom: "1.5rem" }}>
          <h3 style={{ fontSize: "1rem", marginBottom: "1rem" }}>New campaign</h3>
          <div style={{ display: "grid", gap: "0.75rem" }}>
            <input
              placeholder="Name"
              value={formName}
              onChange={e => setFormName(e.target.value)}
              required
              style={{
                padding: "0.5rem 0.75rem",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)",
                background: "var(--bg-secondary)",
                color: "var(--text-primary)",
              }}
            />
            <input
              placeholder="Subject template"
              value={formSubject}
              onChange={e => setFormSubject(e.target.value)}
              style={{
                padding: "0.5rem 0.75rem",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)",
                background: "var(--bg-secondary)",
                color: "var(--text-primary)",
              }}
            />
            <textarea
              placeholder="Body template"
              value={formBody}
              onChange={e => setFormBody(e.target.value)}
              rows={4}
              style={{
                padding: "0.5rem 0.75rem",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)",
                background: "var(--bg-secondary)",
                color: "var(--text-primary)",
              }}
            />
            <textarea
              placeholder="Recipients (comma or newline separated)"
              value={formRecipients}
              onChange={e => setFormRecipients(e.target.value)}
              rows={3}
              style={{
                padding: "0.5rem 0.75rem",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)",
                background: "var(--bg-secondary)",
                color: "var(--text-primary)",
              }}
            />
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busyId === "new"}
              >
                Create
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowForm(false)}
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      )}

      {loading && (
        <p style={{ color: "var(--text-muted)" }}>Loading…</p>
      )}

      <div className="stack">
        {!loading &&
          campaigns.map(campaign => {
            const sc = statusConfig(campaign.status || "draft");
            const rec = recipientCount(campaign.recipients);
            const sent = campaign.total_sent ?? 0;
            const opened = campaign.total_opened ?? 0;
            const replied = campaign.total_replied ?? 0;
            const sentPct = rec > 0 ? (sent / rec) * 100 : 0;
            const openRate = sent > 0 ? Math.round((opened / sent) * 100) : 0;
            const replyRate = sent > 0 ? Math.round((replied / sent) * 100) : 0;
            const id = campaign.campaign_id;
            const busy = busyId === id;

            return (
              <div key={id} className="card">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "flex-start",
                    marginBottom: "1rem",
                  }}
                >
                  <div>
                    <h3 style={{ fontSize: "1rem", fontWeight: 600, marginBottom: "0.25rem" }}>
                      {campaign.name}
                    </h3>
                    <div style={{ fontSize: "0.8125rem", color: "var(--text-muted)" }}>
                      {campaign.created_at ? String(campaign.created_at).slice(0, 10) : ""}{" "}
                      · Subject: <em>{campaign.subject_template || "—"}</em>
                    </div>
                  </div>
                  <span className={`badge ${sc.className}`}>{sc.label}</span>
                </div>

                <div style={{ display: "flex", gap: "2rem", marginBottom: "1rem" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.8125rem" }}>
                    <Users size={14} style={{ color: "var(--text-muted)" }} />
                    <span style={{ color: "var(--text-secondary)" }}>{rec} recipients</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.8125rem" }}>
                    <Send size={14} style={{ color: "var(--text-muted)" }} />
                    <span style={{ color: "var(--text-secondary)" }}>{sent} sent</span>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.8125rem" }}>
                    <Eye size={14} style={{ color: "var(--text-muted)" }} />
                    <span style={{ color: "var(--text-secondary)" }}>
                      {openRate}% opened · {replyRate}% replied
                    </span>
                  </div>
                </div>

                <div style={{ marginBottom: "1rem" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.375rem" }}>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      Delivery progress
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>
                      {sent}/{rec}
                    </span>
                  </div>
                  <div className="progress-bar">
                    <div className="progress-bar-fill" style={{ width: `${sentPct}%` }} />
                  </div>
                </div>

                <div style={{ display: "flex", gap: "0.5rem" }}>
                  {campaign.status === "draft" && (
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={() => handleStart(id)}
                    >
                      <Play size={14} /> Start
                    </button>
                  )}
                  {campaign.status === "active" && (
                    <button
                      type="button"
                      className="btn btn-ghost"
                      disabled={busy}
                      onClick={() => handlePause(id)}
                    >
                      <Pause size={14} /> Pause
                    </button>
                  )}
                  {campaign.status === "paused" && (
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={() => handleStart(id)}
                    >
                      <Play size={14} /> Resume
                    </button>
                  )}
                </div>
              </div>
            );
          })}
      </div>

      {!loading && campaigns.length === 0 && !showForm && (
        <p style={{ color: "var(--text-muted)", marginTop: "1rem" }}>
          No campaigns yet. Create one above.
        </p>
      )}
    </>
  );
}
