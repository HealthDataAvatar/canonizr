#!/usr/bin/env bash
set -euo pipefail

echo "=== Canonizr Pipeline Setup ==="
echo ""

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
echo ""
read -rp "Enable image captioning? (Y/n) " enable_captioning
if [[ "$enable_captioning" =~ ^[Nn]$ ]]; then
  CAPTIONING_ENABLED="false"
  CAPTIONING_VARS=""
else
  CAPTIONING_ENABLED="true"

  DEFAULT_MODEL="/models/gemma-4-e4b.gguf"
  DEFAULT_MMPROJ="/models/gemma-4-e4b-mmproj-f16.gguf"

  echo ""
  echo "Model configuration (paths are inside the container, mapped from ./models/):"
  read -rp "  Model path [$DEFAULT_MODEL]: " model_path
  model_path="${model_path:-$DEFAULT_MODEL}"

  read -rp "  MMProj path [$DEFAULT_MMPROJ]: " mmproj_path
  mmproj_path="${mmproj_path:-$DEFAULT_MMPROJ}"

  read -rp "  Context size [8192]: " ctx_size
  ctx_size="${ctx_size:-8192}"

  read -rp "  Max predict tokens [1024]: " n_predict
  n_predict="${n_predict:-1024}"

  # Check if model files exist locally
  local_model="./models/$(basename "$model_path")"
  local_mmproj="./models/$(basename "$mmproj_path")"

  if [ ! -f "$local_model" ]; then
    echo ""
    echo "Warning: $local_model not found."
    echo "Download your GGUF model file and place it in ./models/"
  fi
  if [ ! -f "$local_mmproj" ]; then
    echo ""
    echo "Warning: $local_mmproj not found."
    echo "Download your mmproj file and place it in ./models/"
  fi

  CAPTIONING_VARS="CAPTIONING_MODEL=$model_path
CAPTIONING_MMPROJ=$mmproj_path
CAPTIONING_CTX_SIZE=$ctx_size
CAPTIONING_N_PREDICT=$n_predict"
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
echo "  Start the pipeline with: ./bin/up.sh"
if [ "$CAPTIONING_ENABLED" = "true" ]; then
  echo "  (captioning service will start automatically)"
fi
