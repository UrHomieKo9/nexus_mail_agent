"use client";

import { useEffect, useState } from "react";
import { Check, X, Edit3, Send } from "lucide-react";
import { useUserId } from "../providers";
import { listDrafts, reviewDraft, sendDraft } from "../lib/api";

type DraftRow = {
  draft_id: string;
  to: string;
  subject: string;
  body: string;
  status: string;
  created_at?: string;
  agent_result?: {
    copywriter?: { tone_match_score?: number };
    critic?: { approved?: boolean; issues?: string[] };
  };
};

function parseDraft(row: any): DraftRow & {
  toneScore: number;
  criticApproved: boolean;
  issues: string[];
} {
  const ar = row.agent_result || {};
  const tone = ar.copywriter?.tone_match_score ?? 0;
  const critic = ar.critic;
  return {
    draft_id: row.draft_id,
    to: row.to || row["to"] || "",
    subject: row.subject || "",
    body: row.body || "",
    status: row.status || "pending",
    created_at: row.created_at,
    agent_result: ar,
    toneScore: typeof tone === "number" ? tone : 0,
    criticApproved: critic?.approved !== false,
    issues: Array.isArray(critic?.issues) ? critic.issues : [],
  };
}

export default function DraftsPage() {
  const { userId } = useUserId();
  const [drafts, setDrafts] = useState<
    ReturnType<typeof parseDraft>[]
  >([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    listDrafts(userId, undefined, 1)
      .then(res => {
        const rows = (res.items || []).map(parseDraft);
        setDrafts(rows);
        setSelectedId(prev => {
          if (prev && rows.some(r => r.draft_id === prev)) return prev;
          return rows[0]?.draft_id ?? null;
        });
      })
      .catch(e =>
        setError(e instanceof Error ? e.message : "Failed to load drafts"),
      )
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [userId]);

  const selected = drafts.find(d => d.draft_id === selectedId);

  async function doReview(
    id: string,
    action: "approved" | "edited" | "rejected",
    editedBody?: string,
  ) {
    setBusy(true);
    setError(null);
    try {
      await reviewDraft(id, action, editedBody);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Review failed");
    } finally {
      setBusy(false);
    }
  }

  async function doSend(id: string) {
    setBusy(true);
    setError(null);
    try {
      await sendDraft(id, true);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Send failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="page-header">
        <h2>Draft Review</h2>
        <p>AI-generated replies from the agent pipeline</p>
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

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "340px 1fr",
          gap: "1.5rem",
        }}
      >
        <div className="card" style={{ padding: 0 }}>
          {loading && (
            <div style={{ padding: "1.5rem", color: "var(--text-muted)" }}>
              Loading…
            </div>
          )}
          {!loading &&
            drafts.map(draft => (
              <div
                key={draft.draft_id}
                className="email-item"
                style={{
                  cursor: "pointer",
                  background:
                    selectedId === draft.draft_id
                      ? "var(--bg-card-hover)"
                      : undefined,
                }}
                onClick={() => setSelectedId(draft.draft_id)}
              >
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: "0.25rem",
                    }}
                  >
                    <span
                      className="email-sender"
                      style={{ fontSize: "0.8125rem" }}
                    >
                      {draft.to}
                    </span>
                  </div>
                  <div
                    className="email-subject"
                    style={{ fontSize: "0.8125rem" }}
                  >
                    {draft.subject}
                  </div>
                  <div
                    style={{
                      marginTop: "0.375rem",
                      display: "flex",
                      gap: "0.375rem",
                      alignItems: "center",
                    }}
                  >
                    <span className={`badge ${draft.status}`}>
                      {draft.status}
                    </span>
                    {!draft.criticApproved && (
                      <span
                        className="badge rejected"
                        style={{ fontSize: "0.6rem" }}
                      >
                        flagged
                      </span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          {!loading && drafts.length === 0 && (
            <div style={{ padding: "1.5rem", color: "var(--text-muted)" }}>
              No drafts yet. Fetch mail and run the AI pipeline from Inbox.
            </div>
          )}
        </div>

        {selected ? (
          <div className="card">
            <div style={{ marginBottom: "1.5rem" }}>
              <div
                style={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "flex-start",
                }}
              >
                <div>
                  <h3
                    style={{
                      fontSize: "1rem",
                      fontWeight: 600,
                      marginBottom: "0.25rem",
                    }}
                  >
                    {selected.subject}
                  </h3>
                  <span
                    style={{
                      fontSize: "0.8125rem",
                      color: "var(--text-muted)",
                    }}
                  >
                    To: {selected.to}
                  </span>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <div className="score-circle">
                    {Math.round((selected.toneScore || 0) * 100)}
                  </div>
                </div>
              </div>
            </div>

            {selected.issues.length > 0 && (
              <div
                style={{
                  background: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid rgba(239, 68, 68, 0.25)",
                  borderRadius: "var(--radius-md)",
                  padding: "0.875rem",
                  marginBottom: "1.5rem",
                }}
              >
                <div
                  style={{
                    fontSize: "0.75rem",
                    fontWeight: 600,
                    color: "var(--danger)",
                    marginBottom: "0.375rem",
                  }}
                >
                  Critic flags
                </div>
                {selected.issues.map((issue, i) => (
                  <div
                    key={i}
                    style={{
                      fontSize: "0.8125rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    • {issue}
                  </div>
                ))}
              </div>
            )}

            <div
              style={{
                background: "var(--bg-secondary)",
                borderRadius: "var(--radius-md)",
                padding: "1.25rem",
                fontFamily: "monospace",
                fontSize: "0.8125rem",
                lineHeight: 1.7,
                whiteSpace: "pre-wrap",
                color: "var(--text-primary)",
                marginBottom: "1.5rem",
                border: "1px solid var(--border)",
              }}
            >
              {selected.body}
            </div>

            {selected.status === "pending" && (
              <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                <button
                  className="btn btn-success"
                  disabled={busy}
                  onClick={() => doReview(selected.draft_id, "approved")}
                >
                  <Check size={14} /> Approve
                </button>
                <button
                  className="btn btn-ghost"
                  disabled={busy}
                  onClick={() => doReview(selected.draft_id, "edited")}
                >
                  <Edit3 size={14} /> Mark edited
                </button>
                <button
                  className="btn btn-danger"
                  disabled={busy}
                  onClick={() => doReview(selected.draft_id, "rejected")}
                >
                  <X size={14} /> Reject
                </button>
                <button
                  className="btn btn-primary"
                  style={{ marginLeft: "auto" }}
                  disabled={busy}
                  onClick={() => doSend(selected.draft_id)}
                >
                  <Send size={14} /> Queue send
                </button>
              </div>
            )}

            {selected.status !== "pending" && (
              <div
                style={{
                  textAlign: "center",
                  padding: "0.75rem",
                  color: "var(--text-muted)",
                }}
              >
                Status: <strong>{selected.status}</strong>
              </div>
            )}
          </div>
        ) : (
          <div className="card empty-state">
            <p>Select a draft to review</p>
          </div>
        )}
      </div>
    </>
  );
}
