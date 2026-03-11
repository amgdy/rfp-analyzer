#!/bin/bash
# =============================================================================
# Dev Container Post-Create Script
# =============================================================================
# Runs after the dev container is created. Installs project dependencies
# and sets up the development environment.


set -e

echo "🚀 Setting up RFP Analyzer development environment..."

# ---------------------------------------------------------------------------
# Install uv (fast Python package manager)
# ---------------------------------------------------------------------------
echo "📦 Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# ---------------------------------------------------------------------------
# Install Python dependencies
# ---------------------------------------------------------------------------
echo "📦 Installing Python dependencies..."
pushd app > /dev/null
uv sync --all-extras --active
popd > /dev/null

# ---------------------------------------------------------------------------
# Set up .env from template if it doesn't exist
# ---------------------------------------------------------------------------
if [ ! -f app/.env ]; then
    echo "📝 Creating .env from template..."
    cp app/.env.example app/.env
    echo "   → Edit app/.env with your Azure credentials"
fi

echo ""
echo "✅ Development environment ready!"
echo ""
echo "Quick start:"
echo "  cd app && uv run streamlit run main.py --server.port=8501"
echo ""
echo "Azure setup:"
echo "  az login          # Authenticate with Azure CLI"
echo "  azd auth login    # Authenticate with Azure Developer CLI"
echo "  azd up            # Provision infrastructure and deploy"
