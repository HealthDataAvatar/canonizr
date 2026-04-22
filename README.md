![Canonizr](web/public/logo.webp)

# Canonizr

Document extraction pipeline. Converts any document into LLM-ready markdown.
Canonizr is part of the [Health Data Avatar](healthdataavatar.com) project, and there are more details available at [Canonizr.com](Canonizr.com).

The entire pipeline can be run on-device, or you can pass certain jobs to external APIs.

## Quick Start

```bash
git clone <repo-url> && cd canonizr-pipelines
./bin/setup.sh
canonizr up
```

Then convert a document:

```bash
canonizr convert document.pdf    # creates document.pdf.md
```

## What it does

Send any file in, get markdown out. PDFs with complex layouts, scanned documents, images, office files. Runs locally by default — optionally use an external API for image captioning.

See [filetypes.md](filetypes.md) for the full list of supported formats.

## CLI

If you have run `./bin/setup.sh` then `canonizr` will be added to your PATH.

```bash
canonizr convert <file>           # writes <file>.md, job JSON to stdout
canonizr convert <file> -o -      # markdown to stdout (for piping)
canonizr convert <file> -o a.md   # custom output path
canonizr convert <file> -f        # overwrite existing output
canonizr convert <file> -q        # quiet, no job JSON
canonizr up [--fg]                # start the pipeline (--fg for logs)
canonizr down                     # stop the pipeline
canonizr health                   # check if the service is running
```

## Web UI

![A screenshot of the Web UI](web/public/ui-screenshot.webp)

The web interface provides drag-and-drop document conversion in the browser. Requires the pipeline to be running.

```bash
cd web
npm install
npm run dev
```

Then open http://localhost:5173.

## Scripts

| Script | Purpose |
|---|---|
| `./bin/setup.sh` | One-time configuration (writes `.env`) |
| `./bin/setup.sh --no-captioning` | Setup without the captioning VLM (~6 GB smaller) |
| `./bin/up.sh` | Start the pipeline (delegates to `canonizr up`) |
| `./bin/down.sh` | Stop the pipeline (delegates to `canonizr down`) |

## Requirements

- Docker + Docker Compose
- ~8 GB disk (~2 GB without captioning)

## Configuration

All configuration lives in `.env`. Copy from `.env.example` or run `./bin/setup.sh`.

### Captioning

Image captioning can run locally or via an external API:

| Mode | Config | Container needed? |
|---|---|---|
| **Off** | `CAPTIONING_ENABLED=false` | No |
| **Local** (default) | `CAPTIONING_ENABLED=true` | Yes — llama.cpp + Gemma 4 (~6 GB) |
| **API** | `CAPTIONING_ENABLED=true` + `CAPTIONING_ENDPOINT` + `CAPTIONING_API_KEY` | No |

For API mode, set these in `.env`:

```env
CAPTIONING_ENABLED=true
CAPTIONING_ENDPOINT=https://api.openai.com/v1/chat/completions  # must end with /chat/completions
CAPTIONING_API_KEY=sk-...
CAPTIONING_API_MODEL=gpt-4o
```

Any OpenAI-compatible endpoint works (OpenAI, Azure OpenAI, Nebius, etc.).

## Architecture

| Service | Role |
|---|---|
| **Gateway** | Format detection, routing, MarkItDown, pymupdf, Pillow |
| **Docling** | PDF layout analysis, table extraction, figure classification |
| **Captioning** | VLM for images, figures, scanned pages (local Gemma 4 or external API) |
| **LibreOffice** | Legacy format conversion (DOC, PPT, XLS, Apple formats) |

Only the gateway port is exposed. All services communicate internally over the Docker network.

## OpenClaw Integration

Canonizr can be used as an OpenClaw skill. See `SKILL.md` for agent integration details.

