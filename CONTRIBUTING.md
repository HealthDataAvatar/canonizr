# Contributing to Canonizr

## Getting Started

```bash
./bin/setup.sh      # generate .env
./bin/up.sh         # start all services
just test           # run tests
just report         # view test results
```

Developers can use [just](https://github.com/casey/just) for convenience, but it's not required — the `bin/` scripts are the primary interface.

## Project Structure

```
cli/                # Thin CLI client
gateway/            # FastAPI gateway (Python)
  app/
    convert.py      # Core conversion logic — start here
    app.py          # FastAPI endpoint
    response.py     # Response dataclass
    prompts.py      # VLM prompts for captioning/transcription
    services/       # HTTP clients for external services
      captioning.py
      docling.py
      libreoffice.py
    imageconv/      # Pillow image format conversion
docling/            # PDF extraction service
libreoffice/        # Legacy format conversion service
models/             # VLM model files (gitignored)
reports/            # Test output (gitignored)
```

**Start with [convert.py](gateway/app/convert.py)** — it's the readable core that shows how every file type is handled.

## Adding a New Service

1. Create a folder with a Dockerfile
2. Add it to `docker-compose.yaml` (no host port mapping — internal only)
3. Add an HTTP client in `gateway/app/services/`
4. Add routing logic in `gateway/app/convert.py`

## Adding a New File Type

1. Identify which service handles it (or if MarkItDown/gateway can do it directly)
2. Add the MIME type to the appropriate set in `gateway/app/convert.py`
3. Update `filetypes.md`

## Running Tests

```bash
just test           # run all tests
just report         # check results
```

Test reports are written to `reports/`.

## Configuration

All configuration lives in `.env` (gitignored). Use `.env.example` as a template, or run `./bin/setup.sh`.

## Style

- Python, favour FastAPI conventions
- Keep services stateless and independently deployable
- The gateway is the only service that knows about other services
- `convert.py` should remain readable — it's the first file anyone inspects
