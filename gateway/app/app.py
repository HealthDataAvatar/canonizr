import os

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import magic
from io import BytesIO

from .convert import convert, UnsupportedFormat, ServiceNotConfigured

app = FastAPI()

CORS_ORIGINS = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "300.0"))

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.post("/convert")
async def convert_document(file: UploadFile = File(...)):
    """Convert a file to markdown."""
    content = BytesIO()
    size = 0

    while True:
        chunk = await file.read(1024 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {MAX_FILE_SIZE // (1024 * 1024)}MB)",
            )
        content.write(chunk)

    content.seek(0)
    file_bytes = content.read()

    mime_type = magic.from_buffer(file_bytes, mime=True)

    try:
        result = await convert(file_bytes, mime_type, file.filename or "document", REQUEST_TIMEOUT)
        result.detected_type = mime_type
        return result.to_dict()
    except UnsupportedFormat as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ServiceNotConfigured as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "ok"}
