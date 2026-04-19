"use client";

import { useEffect, useState } from "react";
import { Users, Building2, ExternalLink } from "lucide-react";
import { useUserId } from "../providers";
import { listLeads } from "../lib/api";

function scoreColor(score: number) {
  if (score >= 0.85) return "var(--success)";
  if (score >= 0.7) return "var(--accent-primary)";
  if (score >= 0.5) return "var(--warning)";
  return "var(--text-muted)";
}

export default function LeadsPage() {
  const { userId } = useUserId();
  const [leads, setLeads] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    listLeads(userId, 1)
      .then(res => setLeads(res.items || []))
      .catch(e =>
        setError(e instanceof Error ? e.message : "Failed to load leads"),
      )
      .finally(() => setLoading(false));
  }, [userId]);

  return (
    <>
      <div className="page-header">
        <h2>Lead Cards</h2>
        <p>Leads stored for this user in Supabase</p>
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

      {loading && (
        <p style={{ color: "var(--text-muted)" }}>Loading…</p>
      )}

      {!loading && leads.length === 0 && (
        <p style={{ color: "var(--text-muted)" }}>
          No leads yet. Use the API{" "}
          <code style={{ fontSize: "0.85em" }}>POST /leads/enrich</code> or seed
          data.
        </p>
      )}

      <div className="grid-2">
        {!loading &&
          leads.map(lead => {
            const score = typeof lead.score === "number" ? lead.score : 0;
            return (
              <div key={lead.lead_id || lead.email} className="card">
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginBottom: "1rem",
                  }}
                >
                  <div>
                    <h3 style={{ fontSize: "1rem", fontWeight: 600 }}>
                      {lead.full_name || lead.email}
                    </h3>
                    <div
                      style={{
                        fontSize: "0.8125rem",
                        color: "var(--text-muted)",
                      }}
                    >
                      {lead.title || "—"}
                    </div>
                  </div>
                  <div
                    className="score-circle"
                    style={{
                      borderColor: scoreColor(score),
                      color: scoreColor(score),
                    }}
                  >
                    {Math.round(score * 100)}
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: "1.5rem",
                    marginBottom: "1rem",
                    fontSize: "0.8125rem",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.375rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Building2 size={14} /> {lead.company || "—"}
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: "0.375rem",
                      color: "var(--text-secondary)",
                    }}
                  >
                    <Users size={14} /> {lead.company_size || "—"}
                  </div>
                </div>

                <div
                  style={{
                    display: "flex",
                    gap: "0.375rem",
                    flexWrap: "wrap",
                    marginBottom: "1rem",
                  }}
                >
                  {lead.industry && (
                    <span className="badge lead">{lead.industry}</span>
                  )}
                  {lead.funding_stage && (
                    <span className="badge follow_up">{lead.funding_stage}</span>
                  )}
                  {lead.estimated_arr && (
                    <span className="badge support">{lead.estimated_arr}</span>
                  )}
                </div>

                {lead.summary && (
                  <p
                    style={{
                      fontSize: "0.8125rem",
                      color: "var(--text-secondary)",
                      lineHeight: 1.5,
                      marginBottom: "1rem",
                    }}
                  >
                    {lead.summary}
                  </p>
                )}

                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    borderTop: "1px solid var(--border)",
                    paddingTop: "0.875rem",
                  }}
                >
                  <div
                    style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}
                  >
                    {lead.email}
                  </div>
                  <span
                    className="btn btn-ghost"
                    style={{ padding: "0.375rem 0.75rem", fontSize: "0.75rem" }}
                  >
                    <ExternalLink size={12} /> Linked
                  </span>
                </div>
              </div>
            );
          })}
      </div>
    </>
  );
}
