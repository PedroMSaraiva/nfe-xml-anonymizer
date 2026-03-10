from __future__ import annotations

import base64

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .pipeline import anonymize_nfe_xml


class AnonymizeRequest(BaseModel):
    xml_base64: str


class AnonymizeResponse(BaseModel):
    anonymized_xml_base64: str
    metadata: dict


app = FastAPI(title="Presidio Anonymization Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/anonymize", response_model=AnonymizeResponse)
def anonymize(payload: AnonymizeRequest) -> AnonymizeResponse:
    try:
        xml_bytes = base64.b64decode(payload.xml_base64)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid base64 payload") from exc

    try:
        anonymized_xml, metadata = anonymize_nfe_xml(xml_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Anonymization failed: {exc}") from exc

    return AnonymizeResponse(
        anonymized_xml_base64=base64.b64encode(anonymized_xml).decode(),
        metadata=metadata,
    )
