#!/usr/bin/env bash
set -euo pipefail

echo "=== Canonizr Pipeline Setup ==="
echo ""

# Install CLI to PATH
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLI_PATH="$SCRIPT_DIR/../cli/canonizr"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/bin}"

if [ -L "$INSTALL_DIR/canonizr" ] && [ "$(readlink "$INSTALL_DIR/canonizr")" = "$CLI_PATH" ]; then
  echo "  canonizr CLI already installed."
else
  read -rp "Install canonizr CLI to $INSTALL_DIR? (Y/n) " install_cli
  if [[ ! "$install_cli" =~ ^[Nn]$ ]]; then
    mkdir -p "$INSTALL_DIR"
    ln -sf "$CLI_PATH" "$INSTALL_DIR/canonizr"
    echo "  canonizr CLI installed to $INSTALL_DIR/canonizr"
    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$INSTALL_DIR"; then
      echo "  Note: $INSTALL_DIR is not on your PATH. Add it with:"
      echo "    export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
  fi
fi

# Parse flags
NO_CAPTIONING=false
for arg in "$@"; do
  case "$arg" in
    --no-captioning) NO_CAPTIONING=true ;;
  esac
done

# Check dependencies
if ! command -v docker &>/dev/null; then
  echo "Error: docker is required but not installed."
  exit 1
fi

# Check for existing .env
if [ -f .env ]; then
  read -rp ".env already exists. Overwrite? (y/N) " overwrite
  if [[ ! "$overwrite" =~ ^[Yy]$ ]]; then
    echo "Keeping existing .env"
    exit 0
  fi
fi

# Captioning setup
if [ "$NO_CAPTIONING" = true ]; then
  enable_captioning="n"
else
  echo ""
  read -rp "Enable image captioning? (Y/n) " enable_captioning
fi
if [[ "$enable_captioning" =~ ^[Nn]$ ]]; then
  CAPTIONING_ENABLED="false"
  CAPTIONING_VARS=""
else
  CAPTIONING_ENABLED="true"

  DEFAULT_MODEL="/models/vision.gguf"
  DEFAULT_MMPROJ="/models/vision.mmproj.gguf"

  MODEL_URL="https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/gemma-4-E4B-it-Q4_K_M.gguf"
  MMPROJ_URL="https://huggingface.co/unsloth/gemma-4-E4B-it-GGUF/resolve/main/mmproj-F16.gguf"

  # Check if model files exist locally, offer to download if missing
  mkdir -p ./models

  if [ ! -f "./models/vision.gguf" ]; then
    echo ""
    echo "Model file not found: ./models/vision.gguf (4.98 GB)"
    read -rp "Download it now? (Y/n) " dl_model
    if [[ ! "$dl_model" =~ ^[Nn]$ ]]; then
      echo "Downloading vision model..."
      curl -L -o ./models/vision.gguf "$MODEL_URL"
    else
      echo "Download it manually:"
      echo "  curl -L -o ./models/vision.gguf $MODEL_URL"
    fi
  fi

  if [ ! -f "./models/vision.mmproj.gguf" ]; then
    echo ""
    echo "Vision projector not found: ./models/vision.mmproj.gguf (990 MB)"
    read -rp "Download it now? (Y/n) " dl_mmproj
    if [[ ! "$dl_mmproj" =~ ^[Nn]$ ]]; then
      echo "Downloading vision projector..."
      curl -L -o ./models/vision.mmproj.gguf "$MMPROJ_URL"
    else
      echo "Download it manually:"
      echo "  curl -L -o ./models/vision.mmproj.gguf $MMPROJ_URL"
    fi
  fi

  CAPTIONING_VARS="CAPTIONING_MODEL=$DEFAULT_MODEL
CAPTIONING_MMPROJ=$DEFAULT_MMPROJ
CAPTIONING_CTX_SIZE=8192
CAPTIONING_N_PREDICT=1024"
fi

# Gateway port
echo ""
read -rp "Gateway port [7005]: " gateway_port
gateway_port="${gateway_port:-7005}"

# Write .env
cat > .env <<EOF
CAPTIONING_ENABLED=$CAPTIONING_ENABLED
GATEWAY_PORT=$gateway_port
EOF

if [ -n "$CAPTIONING_VARS" ]; then
  echo "$CAPTIONING_VARS" >> .env
fi

echo ""
echo "=== Setup complete ==="
echo "  .env written."
echo ""
echo "  Start the pipeline with: canonizr up"
echo "  Stop the pipeline with: canonizr down"
if [ "$CAPTIONING_ENABLED" = "true" ]; then
  echo "  (captioning service will start automatically)"
fi
