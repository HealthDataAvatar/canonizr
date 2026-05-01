import asyncio
import os
import tempfile

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import Response

app = FastAPI()

# LibreOffice headless is not safe to run concurrently in a single container.
_semaphore = asyncio.Semaphore(1)


@app.post("/convert")
async def convert(file: UploadFile = File(...), format: str = "pdf"):
    """Convert a document using headless LibreOffice."""
    async with _semaphore:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, file.filename or "input")
            with open(input_path, "wb") as f:
                f.write(await file.read())

            process = await asyncio.create_subprocess_exec(
                "libreoffice",
                "--headless",
                "--convert-to", format,
                "--outdir", tmpdir,
                input_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=120
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise HTTPException(
                    status_code=504,
                    detail="LibreOffice conversion timed out",
                )

            if process.returncode != 0:
                raise HTTPException(
                    status_code=500,
                    detail=f"LibreOffice conversion failed: {stderr.decode()}",
                )

        # Find the output file
        basename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(tmpdir, f"{basename}.{format}")

        if not os.path.exists(output_path):
            raise HTTPException(
                status_code=500,
                detail="Conversion produced no output file",
            )

        with open(output_path, "rb") as f:
            content = f.read()

        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={"Content-Disposition": f'attachment; filename="{basename}.{format}"'},
        )


@app.get("/health")
async def health():
    return {"status": "ok"}
