"""Transformation functions for NF-e field anonymization."""

import hashlib
import importlib
import math
import random


_fake_instance = None


def _fake():
    global _fake_instance
    if _fake_instance is None:
        faker_module = importlib.import_module("faker")
        _fake_instance = faker_module.Faker("pt_BR")
    return _fake_instance

# IE lengths by UF (Goiás = 9 digits)
_IE_LENGTHS: dict[str, int] = {
    "AC": 13, "AL": 9, "AM": 9, "AP": 9, "BA": 8, "CE": 9, "DF": 13,
    "ES": 9, "GO": 9, "MA": 9, "MG": 13, "MS": 9, "MT": 11, "PA": 9,
    "PB": 9, "PE": 9, "PI": 9, "PR": 10, "RJ": 8, "RN": 10, "RO": 14,
    "RR": 9, "RS": 10, "SC": 9, "SE": 9, "SP": 12, "TO": 11,
}


def hash_with_salt(value: str, salt: str) -> str:
    """SHA-256 hash with salt. Returns 16-char hex digest for readability."""
    return hashlib.sha256(f"{salt}{value}".encode()).hexdigest()[:16]


def faker_person_name() -> str:
    return _fake().name()


def faker_company_name() -> str:
    return _fake().company()


def faker_email() -> str:
    return _fake().email()


def faker_cpf() -> str:
    """Generate a valid fake CPF (digits only)."""
    return _fake().ssn()


def faker_cnpj() -> str:
    """Generate a valid fake CNPJ (digits only)."""
    return _fake().company_id()


def faker_ie(uf: str = "GO") -> str:
    """Generate a plausible fake IE for the given UF."""
    length = _IE_LENGTHS.get(uf, 9)
    return "".join(str(random.randint(0, 9)) for _ in range(length))


def faker_street() -> str:
    return _fake().street_name()


def faker_building_number() -> str:
    return _fake().building_number()


def faker_neighborhood() -> str:
    return _fake().bairro()


def faker_cep() -> str:
    """Generate 8-digit CEP (no dash)."""
    return _fake().postcode(formatted=False)


def faker_phone() -> str:
    """Generate a plausible Brazilian phone number (digits only)."""
    ddd = str(random.randint(11, 99))
    number = "9" + "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"{ddd}{number}"


def mask_phone(value: str) -> str:
    """Mask phone keeping DDD and last 2 digits."""
    digits = "".join(c for c in value if c.isdigit())
    if len(digits) <= 4:
        return "****"
    return digits[:2] + "*" * (len(digits) - 4) + digits[-2:]


def truncate_datetime(value: str) -> str:
    """Round datetime to the hour: 2026-02-24T07:52:00-03:00 → 2026-02-24T07:00:00-03:00."""
    if "T" not in value:
        return value
    date_part, time_tz = value.split("T", 1)
    hour = time_tz[:2]
    # Extract timezone suffix (e.g. -03:00 or Z)
    tz = ""
    for i in range(3, len(time_tz)):
        if time_tz[i] in "+-":
            tz = time_tz[i:]
            break
    if not tz and time_tz.endswith("Z"):
        tz = "Z"
    return f"{date_part}T{hour}:00:00{tz}"


def _laplace_sample(scale: float) -> float:
    """Sample from Laplace(0, scale) distribution."""
    u = random.uniform(-0.5, 0.5)
    return -scale * math.copysign(1.0, u) * math.log1p(-2.0 * abs(u))


def add_dp_noise(value: str, epsilon: float) -> str:
    """Add calibrated Laplacian noise for ε-differential privacy."""
    try:
        num = float(value)
        sensitivity = max(abs(num) * 0.01, 0.01)
        noise = _laplace_sample(sensitivity / epsilon)
        result = max(0.0, round(num + noise, 2))
        return f"{result:.2f}"
    except (ValueError, TypeError):
        return value


def value_range(value: str) -> str:
    """Generalize a monetary value into a range bucket."""
    try:
        num = float(value)
        if num <= 1_000:
            return "0.00-1000.00"
        if num <= 10_000:
            return "1000.00-10000.00"
        if num <= 100_000:
            return "10000.00-100000.00"
        return "100000.00+"
    except (ValueError, TypeError):
        return value
