from __future__ import annotations

import base64

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .config import settings


app = FastAPI(title="NF-e Anonymization API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/process")
async def process(files: list[UploadFile] = File(...)) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No XML files provided")
    if len(files) > 5:
        raise HTTPException(status_code=400, detail="Maximum 5 XML files per request")

    results: list[dict] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        for file in files:
            filename = file.filename or "upload.xml"
            if not filename.lower().endswith(".xml"):
                raise HTTPException(status_code=400, detail=f"Invalid file type: {filename}")

            original_bytes = await file.read()
            payload = {"xml_base64": base64.b64encode(original_bytes).decode()}

            try:
                response = await client.post(f"{settings.presidio_url}/anonymize", json=payload)
            except httpx.HTTPError as exc:
                raise HTTPException(status_code=502, detail="Presidio service unavailable") from exc

            if response.status_code != 200:
                detail = response.text
                raise HTTPException(status_code=400, detail=f"Failed on {file.filename}: {detail}")

            data = response.json()
            anonymized_bytes = base64.b64decode(data["anonymized_xml_base64"])

            results.append(
                {
                    "filename": filename,
                    "original_xml": original_bytes.decode("utf-8", errors="replace"),
                    "anonymized_xml": anonymized_bytes.decode("utf-8", errors="replace"),
                    "metadata": data.get("metadata", {}),
                }
            )

    return {"count": len(results), "results": results}
