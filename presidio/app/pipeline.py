"""NF-e anonymization pipeline using lxml for XML round-trip fidelity."""

from __future__ import annotations

from typing import Any
from xml.etree import ElementTree as ET

from .config import settings
from .recognizers import analyze_free_text
from .transforms import (
    add_dp_noise,
    faker_cep,
    faker_company_name,
    faker_email,
    faker_neighborhood,
    faker_person_name,
    faker_phone,
    faker_street,
    hash_with_salt,
    truncate_datetime,
    value_range,
)

NFE_NS = "http://www.portalfiscal.inf.br/nfe"
SIG_NS = "http://www.w3.org/2000/09/xmldsig#"
NS = {"nfe": NFE_NS, "ds": SIG_NS}


def _find(parent: Any, tag: str) -> Any | None:
    return parent.find(f"nfe:{tag}", NS)


def _set(parent: Any, tag: str, value: str) -> bool:
    el = parent.find(f"nfe:{tag}", NS)
    if el is not None and el.text is not None:
        el.text = value
        return True
    return False


def _get(parent: Any, tag: str) -> str | None:
    el = parent.find(f"nfe:{tag}", NS)
    return el.text if el is not None else None


def _anonymize_address(
    parent: Any,
    path_prefix: str,
    metadata: dict,
) -> None:
    """Anonymize an enderEmit or enderDest block with fake but plausible data."""
    if _set(parent, "xLgr", faker_street()):
        metadata["fields_anonymized"].append(f"{path_prefix}/xLgr")
    if _set(parent, "nro", "0"):
        metadata["fields_anonymized"].append(f"{path_prefix}/nro")
    if _set(parent, "xCpl", "[REDACTED]"):
        metadata["fields_anonymized"].append(f"{path_prefix}/xCpl")
    if _set(parent, "xBairro", faker_neighborhood()):
        metadata["fields_anonymized"].append(f"{path_prefix}/xBairro")
    if _set(parent, "CEP", faker_cep()):
        metadata["fields_anonymized"].append(f"{path_prefix}/CEP")
    if _set(parent, "fone", faker_phone()):
        metadata["fields_anonymized"].append(f"{path_prefix}/fone")


def _anonymize_emit(emit: Any, salt: str, metadata: dict) -> None:
    """Anonymize emitter (emit) section."""
    # CNPJ → hash
    cnpj = _get(emit, "CNPJ")
    if cnpj:
        _set(emit, "CNPJ", hash_with_salt(cnpj, salt))
        metadata["fields_anonymized"].append("emit/CNPJ")

    # Names → faker
    if _set(emit, "xNome", faker_company_name()):
        metadata["fields_anonymized"].append("emit/xNome")
    if _set(emit, "xFant", faker_company_name()):
        metadata["fields_anonymized"].append("emit/xFant")

    # IE, IM → hash
    ie = _get(emit, "IE")
    if ie:
        _set(emit, "IE", hash_with_salt(ie, salt))
        metadata["fields_anonymized"].append("emit/IE")
    im = _get(emit, "IM")
    if im:
        _set(emit, "IM", hash_with_salt(im, salt))
        metadata["fields_anonymized"].append("emit/IM")

    # Address
    ender = _find(emit, "enderEmit")
    if ender is not None:
        _anonymize_address(ender, "emit/enderEmit", metadata)


def _anonymize_dest(dest: Any, salt: str, metadata: dict) -> None:
    """Anonymize recipient (dest) section."""
    # CPF or CNPJ → hash
    cpf = _get(dest, "CPF")
    if cpf:
        _set(dest, "CPF", hash_with_salt(cpf, salt))
        metadata["fields_anonymized"].append("dest/CPF")
    cnpj = _get(dest, "CNPJ")
    if cnpj:
        _set(dest, "CNPJ", hash_with_salt(cnpj, salt))
        metadata["fields_anonymized"].append("dest/CNPJ")

    # Name → faker (person for CPF, company for CNPJ)
    if cpf:
        if _set(dest, "xNome", faker_person_name()):
            metadata["fields_anonymized"].append("dest/xNome")
    else:
        if _set(dest, "xNome", faker_company_name()):
            metadata["fields_anonymized"].append("dest/xNome")

    # Email → faker
    if _set(dest, "email", faker_email()):
        metadata["fields_anonymized"].append("dest/email")

    # IE → hash
    ie = _get(dest, "IE")
    if ie:
        _set(dest, "IE", hash_with_salt(ie, salt))
        metadata["fields_anonymized"].append("dest/IE")

    # Address
    ender = _find(dest, "enderDest")
    if ender is not None:
        _anonymize_address(ender, "dest/enderDest", metadata)


def _anonymize_det(det: Any, epsilon: float, metadata: dict) -> None:
    """Anonymize a single det (line item) block — DP noise on monetary values."""
    n_item = det.get("nItem", "?")
    prod = _find(det, "prod")
    if prod is None:
        return
    for tag in ["vUnCom", "vProd", "vUnTrib", "vFrete", "vSeg", "vDesc", "vOutro"]:
        el = prod.find(f"nfe:{tag}", NS)
        if el is not None and el.text:
            el.text = add_dp_noise(el.text, epsilon)
            metadata["fields_anonymized"].append(f"det[{n_item}]/prod/{tag}")

    # Redact order reference (can link back to original order)
    if _set(prod, "xPed", "[REDACTED]"):
        metadata["fields_anonymized"].append(f"det[{n_item}]/prod/xPed")


def _anonymize_totals(total: Any, epsilon: float, metadata: dict) -> None:
    """Anonymize total values — vNF gets range, rest get DP noise."""
    icms_tot = _find(total, "ICMSTot")
    if icms_tot is None:
        return

    # vNF → value range (per technical decision document)
    vnf = _get(icms_tot, "vNF")
    if vnf:
        _set(icms_tot, "vNF", value_range(vnf))
        metadata["fields_anonymized"].append("total/ICMSTot/vNF")

    # Other totals → DP noise
    for tag in ["vBC", "vICMS", "vProd", "vFrete", "vSeg", "vDesc", "vII",
                "vIPI", "vPIS", "vCOFINS", "vOutro", "vTotTrib"]:
        el = icms_tot.find(f"nfe:{tag}", NS)
        if el is not None and el.text:
            el.text = add_dp_noise(el.text, epsilon)
            metadata["fields_anonymized"].append(f"total/ICMSTot/{tag}")


def _anonymize_transp(transp: Any, salt: str, metadata: dict) -> None:
    """Anonymize transport section."""
    transporta = _find(transp, "transporta")
    if transporta is None:
        return
    cpf = _get(transporta, "CPF")
    if cpf:
        _set(transporta, "CPF", hash_with_salt(cpf, salt))
        metadata["fields_anonymized"].append("transp/transporta/CPF")
    cnpj = _get(transporta, "CNPJ")
    if cnpj:
        _set(transporta, "CNPJ", hash_with_salt(cnpj, salt))
        metadata["fields_anonymized"].append("transp/transporta/CNPJ")
    if _set(transporta, "xNome", faker_company_name()):
        metadata["fields_anonymized"].append("transp/transporta/xNome")
    ie = _get(transporta, "IE")
    if ie:
        _set(transporta, "IE", hash_with_salt(ie, salt))
        metadata["fields_anonymized"].append("transp/transporta/IE")
    if _set(transporta, "xEnder", faker_street()):
        metadata["fields_anonymized"].append("transp/transporta/xEnder")


def _anonymize_inf_adic(inf_adic: Any, metadata: dict) -> None:
    """Run NLP analysis on free-text fields."""
    inf_cpl = _find(inf_adic, "infCpl")
    if inf_cpl is not None and inf_cpl.text:
        anonymized_text, entity_counts = analyze_free_text(inf_cpl.text)
        inf_cpl.text = anonymized_text
        metadata["fields_anonymized"].append("infAdic/infCpl")
        metadata["entities_detected_in_free_text"] = entity_counts


def _anonymize_prot(prot: Any, metadata: dict) -> None:
    """Anonymize protNFe section."""
    inf_prot = _find(prot, "infProt")
    if inf_prot is None:
        return
    if _set(inf_prot, "chNFe", "0" * 44):
        metadata["fields_anonymized"].append("protNFe/infProt/chNFe")
    el = inf_prot.find(f"nfe:dhRecbto", NS)
    if el is not None and el.text:
        el.text = truncate_datetime(el.text)
        metadata["fields_anonymized"].append("protNFe/infProt/dhRecbto")
    if _set(inf_prot, "nProt", "0" * 15):
        metadata["fields_anonymized"].append("protNFe/infProt/nProt")
    if _set(inf_prot, "digVal", "[REDACTED]"):
        metadata["fields_anonymized"].append("protNFe/infProt/digVal")


def _remove_signature(nfe: Any) -> bool:
    """Remove XML digital signature (contains PII in X509Certificate)."""
    sig = nfe.find(f"{{{SIG_NS}}}Signature")
    if sig is not None:
        nfe.remove(sig)
        return True
    return False


# ── Public API ──────────────────────────────────────────────────────────────


def anonymize_nfe_xml(xml_bytes: bytes) -> tuple[bytes, dict]:
    """Anonymize an NF-e XML document.

    Args:
        xml_bytes: Raw XML bytes of the NF-e.

    Returns:
        Tuple of (anonymized_xml_bytes, metadata_dict).
    """
    salt = settings.hash_salt
    epsilon = settings.dp_epsilon

    root = ET.fromstring(xml_bytes)
    metadata: dict = {"fields_anonymized": [], "entities_detected_in_free_text": {}}

    # Navigate to infNFe (handles both nfeProc>NFe>infNFe and NFe>infNFe)
    inf_nfe = root.find(f".//{{{NFE_NS}}}infNFe")
    if inf_nfe is None:
        raise ValueError("Invalid NF-e XML: <infNFe> element not found")

    # 1. Chave de acesso in @Id attribute
    old_id = inf_nfe.get("Id")
    if old_id:
        inf_nfe.set("Id", "NFe" + "0" * 44)
        metadata["fields_anonymized"].append("infNFe/@Id")

    # 2. ide — truncate datetimes
    ide = _find(inf_nfe, "ide")
    if ide is not None:
        for tag in ["dhEmi", "dhSaiEnt"]:
            el = ide.find(f"nfe:{tag}", NS)
            if el is not None and el.text:
                el.text = truncate_datetime(el.text)
                metadata["fields_anonymized"].append(f"ide/{tag}")

    # 3. emit
    emit = _find(inf_nfe, "emit")
    if emit is not None:
        _anonymize_emit(emit, salt, metadata)

    # 4. dest
    dest = _find(inf_nfe, "dest")
    if dest is not None:
        _anonymize_dest(dest, salt, metadata)

    # 5. det items (may be multiple)
    for det in inf_nfe.findall(f"nfe:det", NS):
        _anonymize_det(det, epsilon, metadata)

    # 6. total
    total = _find(inf_nfe, "total")
    if total is not None:
        _anonymize_totals(total, epsilon, metadata)

    # 7. transp
    transp = _find(inf_nfe, "transp")
    if transp is not None:
        _anonymize_transp(transp, salt, metadata)

    # 8. pag — apply DP noise to payment values
    pag = _find(inf_nfe, "pag")
    if pag is not None:
        for det_pag in pag.findall(f"nfe:detPag", NS):
            el = det_pag.find(f"nfe:vPag", NS)
            if el is not None and el.text:
                el.text = add_dp_noise(el.text, epsilon)
                metadata["fields_anonymized"].append("pag/detPag/vPag")

    # 9. infAdic — NLP analysis on free text
    inf_adic = _find(inf_nfe, "infAdic")
    if inf_adic is not None:
        _anonymize_inf_adic(inf_adic, metadata)

    # 10. Remove Signature (contains PII in certificate)
    nfe_elem = root.find(f"{{{NFE_NS}}}NFe")
    if nfe_elem is not None and _remove_signature(nfe_elem):
        metadata["fields_anonymized"].append("Signature (removed)")

    # 11. Update Signature Reference URI if it survived
    for ref in root.findall(f".//{{{SIG_NS}}}Reference"):
        uri = ref.get("URI", "")
        if uri.startswith("#NFe"):
            ref.set("URI", "#NFe" + "0" * 44)

    # 12. protNFe
    prot = root.find(f".//{{{NFE_NS}}}protNFe")
    if prot is not None:
        _anonymize_prot(prot, metadata)

    xml_out = ET.tostring(root, encoding="UTF-8", xml_declaration=True)
    return xml_out, metadata
