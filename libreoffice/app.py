import os
import subprocess
import tempfile

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import FileResponse

app = FastAPI()


@app.post("/convert")
async def convert(file: UploadFile = File(...), format: str = "pdf"):
    """Convert a document using headless LibreOffice."""
    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, file.filename or "input")
        with open(input_path, "wb") as f:
            f.write(await file.read())

        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", format,
                "--outdir", tmpdir,
                input_path,
            ],
            capture_output=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"LibreOffice conversion failed: {result.stderr.decode()}",
            )

        # Find the output file
        basename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(tmpdir, f"{basename}.{format}")

        if not os.path.exists(output_path):
            raise HTTPException(
                status_code=500,
                detail=f"Conversion produced no output file",
            )

        return FileResponse(
            output_path,
            media_type="application/octet-stream",
            filename=f"{basename}.{format}",
        )


@app.get("/health")
async def health():
    return {"status": "ok"}
