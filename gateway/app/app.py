import asyncio
import json
import logging
import os
import time

import xxhash

from fastapi import FastAPI, File, Header, Query, Request, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
import magic
from io import BytesIO

from .convert import convert, UnsupportedFormat, ServiceNotConfigured
from .services.image_postprocess import CaptioningUpstreamError
from .tracing import Trace

logger = logging.getLogger(__name__)

app = FastAPI()

DEBUG_MODE = os.environ.get("DEBUG", "").lower() in ("1", "true", "yes")
CORS_ORIGINS = [o for o in os.environ.get("CORS_ORIGINS", "").split(",") if o]
MAX_FILE_SIZE = int(os.environ.get("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024
REQUEST_TIMEOUT = float(os.environ.get("REQUEST_TIMEOUT", "300.0"))
_convert_semaphore = asyncio.Semaphore(int(os.environ.get("MAX_CONCURRENT_CONVERSIONS", "4")))

SANITISED_MESSAGES = {
    429: "Upstream rate limit exceeded",
    500: "Internal processing error",
    502: "Upstream service error",
    504: "Upstream service timeout",
}

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.exception_handler(HTTPException)
async def sanitise_errors(request: Request, exc: HTTPException):
    """In production, strip internal details from error responses."""
    if DEBUG_MODE:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.error("HTTP %d: %s", exc.status_code, exc.detail)
    safe_message = SANITISED_MESSAGES.get(exc.status_code, exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"detail": safe_message})


ECHO_HEADERS = {"x-subscription-id", "x-org-id", "x-request-id"}


@app.post("/convert")
async def convert_document(
    request: Request,
    file: UploadFile = File(...),
    verbose: bool = Query(False),
    accept: str = Header("application/json"),
):
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

    trace = Trace("request", file_size_bytes=size, mime_type=mime_type, filename=file.filename or "document")

    async with _convert_semaphore:
        try:
            deadline = time.monotonic() + REQUEST_TIMEOUT
            result = await convert(file_bytes, mime_type, file.filename or "document", deadline, trace)
            trace.finish()
            result.detected_type = mime_type
            result.input_bytes = len(file_bytes)
            result.input_hash = xxhash.xxh64(file_bytes).hexdigest()
            result.trace = trace.to_dict()

            echo = {k: v for k, v in request.headers.items() if k.lower() in ECHO_HEADERS}
            headers = {**result.audit_headers(), **echo, "X-Job-Metadata": result.metadata_json()}

            if "text/markdown" in accept:
                return Response(
                    content=result.markdown,
                    media_type="text/markdown; charset=utf-8",
                    headers=headers,
                )

            return Response(
                content=json.dumps(result.to_dict(verbose=verbose)),
                media_type="application/json",
                headers=headers,
            )
        except CaptioningUpstreamError as e:
            raise HTTPException(status_code=500, detail=str(e))
        except UnsupportedFormat as e:
            raise HTTPException(status_code=400, detail=str(e))
        except ServiceNotConfigured as e:
            raise HTTPException(status_code=422, detail=str(e))


@app.get("/health")
async def health_check():
    return {"status": "ok"}
