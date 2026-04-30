"use client";

import { useEffect, useState } from "react";
import { Mail, ShieldCheck, ExternalLink, AlertCircle, CheckCircle2 } from "lucide-react";
import { connectProvider, listConnectedAccounts } from "../lib/api";
import { useUserId } from "../providers";

export default function SettingsPage() {
  const { userId, setUserId } = useUserId();
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [accounts, setAccounts] = useState<{
    gmail: { connected: boolean; email: string | null };
    outlook: { connected: boolean; email: string | null };
  } | null>(null);

  const fetchAccounts = async () => {
    try {
      const data = await listConnectedAccounts(userId);
      setAccounts(data);
    } catch (e) {
      console.error("Failed to fetch accounts", e);
    }
  };

  useEffect(() => {
    fetchAccounts();
    
    // Check for success/error params in URL
    const params = new URLSearchParams(window.location.search);
    const success = params.get("success") === "true";
    const newUserId = params.get("user_id");

    if (success && newUserId) {
      setUserId(newUserId);
      // Clean up the URL to remove the sensitive user_id/tokens params
      window.history.replaceState({}, document.title, window.location.pathname);
    } else if (params.get("error")) {
      setError(params.get("error"));
    }
  }, [userId, setUserId]);

  const handleConnect = async (provider: "gmail" | "outlook") => {
    setLoading(provider);
    setError(null);
    try {
      const redirectUri = `${window.location.origin.replace("3000", "8000")}/api/v1/auth/callback/${provider}`;
      const { authorization_url } = await connectProvider(provider, redirectUri);
      window.location.href = authorization_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to initiate connection");
      setLoading(provider === "gmail" ? "gmail" : "outlook"); // Keep loading state to show error
      setLoading(null);
    }
  };

  return (
    <div className="settings-container">
      <div className="page-header">
        <h2>Settings & Connections</h2>
        <p>Manage your email accounts and platform security</p>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--danger)", color: "var(--danger)", marginBottom: "1.5rem" }}>
          <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
            <AlertCircle size={18} />
            <span>{error}</span>
          </div>
        </div>
      )}

      <div className="settings-grid">
        <section className="settings-section">
          <div className="section-header">
            <Mail className="section-icon" />
            <h3>Email Connections</h3>
          </div>
          <p className="section-desc">Connect your primary outreach accounts to start fetching and sending emails.</p>

          <div className="connection-cards">
            {/* Gmail Card */}
            <div className={`connection-card ${accounts?.gmail.connected ? 'connected' : ''}`}>
              <div className="connection-info">
                <div className="provider-logo gmail">G</div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <h4>Google Gmail</h4>
                    {accounts?.gmail.connected && <CheckCircle2 size={16} className="success-icon" />}
                  </div>
                  <p>{accounts?.gmail.connected ? accounts.gmail.email : "Read, write, and send access"}</p>
                </div>
              </div>
              <button
                className={`btn ${accounts?.gmail.connected ? 'btn-ghost' : 'btn-primary'}`}
                onClick={() => handleConnect("gmail")}
                disabled={loading === "gmail"}
              >
                {loading === "gmail" ? "Connecting..." : accounts?.gmail.connected ? "Reconnect" : "Connect Gmail"}
                <ExternalLink size={14} style={{ marginLeft: "0.5rem" }} />
              </button>
            </div>

            {/* Outlook Card */}
            <div className={`connection-card ${accounts?.outlook.connected ? 'connected' : ''}`}>
              <div className="connection-info">
                <div className="provider-logo outlook">O</div>
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <h4>Microsoft Outlook</h4>
                    {accounts?.outlook.connected && <CheckCircle2 size={16} className="success-icon" />}
                  </div>
                  <p>{accounts?.outlook.connected ? accounts.outlook.email : "Read, write, and send access"}</p>
                </div>
              </div>
              <button
                className={`btn ${accounts?.outlook.connected ? 'btn-ghost' : 'btn-ghost'}`}
                onClick={() => handleConnect("outlook")}
                disabled={loading === "outlook"}
              >
                {loading === "outlook" ? "Connecting..." : accounts?.outlook.connected ? "Reconnect" : "Connect Outlook"}
                <ExternalLink size={14} style={{ marginLeft: "0.5rem" }} />
              </button>
            </div>
          </div>
        </section>

        <section className="settings-section">
          <div className="section-header">
            <ShieldCheck className="section-icon" />
            <h3>Security & API</h3>
          </div>
          <p className="section-desc">Technical configuration and security audit status.</p>

          <div className="card bg-secondary">
            <div className="security-item">
              <span className="label">OAuth Scope</span>
              <span className="value badge">Full Access</span>
            </div>
            <div className="security-item">
              <span className="label">Encryption</span>
              <span className="value badge success">AES-256 Enabled</span>
            </div>
            <div className="security-item">
              <span className="label">Last Audit</span>
              <span className="value">April 26, 2026</span>
            </div>
          </div>
        </section>
      </div>

      <style jsx>{`
        .settings-container {
          max-width: 900px;
          margin: 0 auto;
        }
        .settings-grid {
          display: grid;
          gap: 2rem;
          margin-top: 1rem;
        }
        .settings-section {
          background: var(--bg-card);
          padding: 1.5rem;
          border-radius: var(--radius-lg);
          border: 1px solid var(--border);
        }
        .section-header {
          display: flex;
          align-items: center;
          gap: 0.75rem;
          margin-bottom: 0.5rem;
        }
        .section-icon {
          color: var(--primary);
        }
        .section-desc {
          color: var(--text-muted);
          font-size: 0.875rem;
          margin-bottom: 1.5rem;
        }
        .connection-cards {
          display: grid;
          gap: 1rem;
        }
        .connection-card {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 1.25rem;
          background: var(--bg-secondary);
          border-radius: var(--radius-md);
          border: 1px solid var(--border);
          transition: all 0.2s ease;
        }
        .connection-card.connected {
          border-color: var(--success);
          background: rgba(16, 185, 129, 0.05);
        }
        .connection-card:hover {
          border-color: var(--primary-light);
          transform: translateY(-2px);
        }
        .connection-info {
          display: flex;
          gap: 1rem;
          align-items: center;
        }
        .provider-logo {
          width: 40px;
          height: 40px;
          border-radius: 8px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-weight: bold;
          font-size: 1.25rem;
          color: white;
        }
        .provider-logo.gmail { background: #ea4335; }
        .provider-logo.outlook { background: #0078d4; }
        
        .connection-info h4 {
          margin: 0;
          font-size: 1rem;
        }
        .connection-info p {
          margin: 0;
          font-size: 0.75rem;
          color: var(--text-muted);
        }
        
        .security-item {
          display: flex;
          justify-content: space-between;
          padding: 0.75rem 0;
          border-bottom: 1px solid var(--border);
        }
        .security-item:last-child { border-bottom: none; }
        .security-item .label { font-size: 0.875rem; color: var(--text-secondary); }
        .security-item .value { font-size: 0.875rem; font-weight: 500; }
        .success { color: var(--success); }
        .success-icon { color: var(--success); }
      `}</style>
    </div>
  );
}
