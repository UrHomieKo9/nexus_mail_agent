#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────
#  Cloudflare Tunnel Setup for Nexus Mail Agent
#  Exposes local FastAPI (8000) and Next.js (3000) to the
#  internet for OAuth callbacks and webhook testing.
# ─────────────────────────────────────────────────────────

set -euo pipefail

TUNNEL_NAME="${TUNNEL_NAME:-nexus-mail-agent}"
API_PORT="${API_PORT:-8000}"
DASHBOARD_PORT="${DASHBOARD_PORT:-3000}"

# ── 1. Install cloudflared if not present ──

if ! command -v cloudflared &> /dev/null; then
    echo "▸ Installing cloudflared..."

    OS=$(uname -s | tr '[:upper:]' '[:lower:]')
    ARCH=$(uname -m)

    case "$ARCH" in
        x86_64) ARCH="amd64" ;;
        aarch64|arm64) ARCH="arm64" ;;
    esac

    if [ "$OS" = "linux" ]; then
        curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${ARCH}" \
            -o /usr/local/bin/cloudflared
        chmod +x /usr/local/bin/cloudflared
    elif [ "$OS" = "darwin" ]; then
        brew install cloudflare/cloudflare/cloudflared 2>/dev/null || \
        curl -fsSL "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-darwin-${ARCH}.tgz" | \
            tar xz -C /usr/local/bin/
    else
        echo "✗ Unsupported OS: $OS. Please install cloudflared manually."
        echo "  https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/"
        exit 1
    fi

    echo "  ✓ cloudflared installed: $(cloudflared --version)"
else
    echo "  ✓ cloudflared already installed: $(cloudflared --version)"
fi

# ── 2. Authenticate (first time only) ──

if [ ! -f "$HOME/.cloudflared/cert.pem" ]; then
    echo ""
    echo "▸ Authenticating with Cloudflare..."
    echo "  A browser window will open. Log in and authorize."
    cloudflared tunnel login
    echo "  ✓ Authenticated"
fi

# ── 3. Create tunnel (if it doesn't exist) ──

if ! cloudflared tunnel list 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    echo ""
    echo "▸ Creating tunnel: $TUNNEL_NAME"
    cloudflared tunnel create "$TUNNEL_NAME"
    echo "  ✓ Tunnel created"
else
    echo "  ✓ Tunnel '$TUNNEL_NAME' already exists"
fi

# ── 4. Generate config file ──

TUNNEL_ID=$(cloudflared tunnel list 2>/dev/null | grep "$TUNNEL_NAME" | awk '{print $1}')
CONFIG_DIR="$HOME/.cloudflared"
CONFIG_FILE="$CONFIG_DIR/config-${TUNNEL_NAME}.yml"

cat > "$CONFIG_FILE" << EOF
tunnel: ${TUNNEL_ID}
credentials-file: ${CONFIG_DIR}/${TUNNEL_ID}.json

ingress:
  # FastAPI backend
  - hostname: api-${TUNNEL_NAME}.your-domain.com
    service: http://localhost:${API_PORT}

  # Next.js dashboard
  - hostname: app-${TUNNEL_NAME}.your-domain.com
    service: http://localhost:${DASHBOARD_PORT}

  # Catch-all (required by cloudflared)
  - service: http_status:404
EOF

echo ""
echo "  ✓ Config written to: $CONFIG_FILE"
echo ""
echo "─────────────────────────────────────────────"
echo "  Tunnel ID:    $TUNNEL_ID"
echo "  Config file:  $CONFIG_FILE"
echo ""
echo "  NEXT STEPS:"
echo "  1. Update the hostnames in $CONFIG_FILE"
echo "     to match your Cloudflare DNS domain."
echo ""
echo "  2. Add DNS CNAME records:"
echo "     cloudflared tunnel route dns $TUNNEL_NAME api-${TUNNEL_NAME}.your-domain.com"
echo "     cloudflared tunnel route dns $TUNNEL_NAME app-${TUNNEL_NAME}.your-domain.com"
echo ""
echo "  3. Start the tunnel:"
echo "     cloudflared tunnel --config $CONFIG_FILE run"
echo ""
echo "  4. Update your .env:"
echo "     CORS_ORIGINS=https://app-${TUNNEL_NAME}.your-domain.com"
echo "─────────────────────────────────────────────"
