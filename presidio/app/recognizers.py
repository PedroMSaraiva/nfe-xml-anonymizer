from __future__ import annotations

import importlib
from typing import Any

from .config import settings


def _valid_cpf(text: str) -> bool:
    digits = [int(c) for c in text if c.isdigit()]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    total = sum(d * (10 - i) for i, d in enumerate(digits[:9]))
    r1 = (total * 10 % 11) % 10
    if r1 != digits[9]:
        return False
    total = sum(d * (11 - i) for i, d in enumerate(digits[:10]))
    r2 = (total * 10 % 11) % 10
    return r2 == digits[10]


def _valid_cnpj(text: str) -> bool:
    digits = [int(c) for c in text if c.isdigit()]
    if len(digits) != 14 or len(set(digits)) == 1:
        return False
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    t = sum(x * w for x, w in zip(digits[:12], w1))
    r = t % 11
    c1 = 0 if r < 2 else 11 - r
    if c1 != digits[12]:
        return False
    t = sum(x * w for x, w in zip(digits[:13], w2))
    r = t % 11
    c2 = 0 if r < 2 else 11 - r
    return c2 == digits[13]


_analyzer: Any = None
_anonymizer: Any = None
_operator_config_cls: Any = None


def _ensure_engines() -> tuple[Any, Any, Any]:
    global _analyzer
    global _anonymizer
    global _operator_config_cls

    if _analyzer is None or _anonymizer is None or _operator_config_cls is None:
        analyzer_mod = importlib.import_module("presidio_analyzer")
        nlp_mod = importlib.import_module("presidio_analyzer.nlp_engine")
        anonymizer_mod = importlib.import_module("presidio_anonymizer")
        entities_mod = importlib.import_module("presidio_anonymizer.entities")

        AnalyzerEngine = analyzer_mod.AnalyzerEngine
        Pattern = analyzer_mod.Pattern
        PatternRecognizer = analyzer_mod.PatternRecognizer
        RecognizerRegistry = analyzer_mod.RecognizerRegistry
        NlpEngineProvider = nlp_mod.NlpEngineProvider
        AnonymizerEngine = anonymizer_mod.AnonymizerEngine
        OperatorConfig = entities_mod.OperatorConfig

        cpf_recognizer = PatternRecognizer(
            supported_entity="BR_CPF",
            supported_language="en",
            patterns=[
                Pattern("cpf_fmt", r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", 0.8),
                Pattern("cpf_raw", r"\b\d{11}\b", 0.3),
            ],
            context=["cpf", "cadastro", "contribuinte", "pessoa", "cliente"],
        )

        cnpj_recognizer = PatternRecognizer(
            supported_entity="BR_CNPJ",
            supported_language="en",
            patterns=[
                Pattern("cnpj_fmt", r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", 0.8),
                Pattern("cnpj_raw", r"\b\d{14}\b", 0.3),
            ],
            context=["cnpj", "empresa", "emitente", "destinatário", "razão social"],
        )

        phone_recognizer = PatternRecognizer(
            supported_entity="BR_PHONE",
            supported_language="en",
            patterns=[
                Pattern("phone_br", r"\b(?:\+55\s?)?\(?\d{2}\)?\s?\d{4,5}-?\d{4}\b", 0.5),
                Pattern("celular", r"(?i)celular:?\s*(\d{10,11})", 0.9),
            ],
            context=["telefone", "celular", "fone", "tel", "contato"],
        )

        email_recognizer = PatternRecognizer(
            supported_entity="BR_EMAIL",
            supported_language="en",
            patterns=[
                Pattern("email", r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", 0.8),
            ],
            context=["email", "e-mail", "correio"],
        )

        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": settings.spacy_model}],
            }
        )
        nlp_engine = provider.create_engine()

        registry = RecognizerRegistry()
        registry.add_recognizer(cpf_recognizer)
        registry.add_recognizer(cnpj_recognizer)
        registry.add_recognizer(phone_recognizer)
        registry.add_recognizer(email_recognizer)

        _analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["en"], registry=registry)
        _anonymizer = AnonymizerEngine()
        _operator_config_cls = OperatorConfig

    return _analyzer, _anonymizer, _operator_config_cls


def analyze_free_text(text: str) -> tuple[str, dict[str, int]]:
    analyzer, anonymizer, OperatorConfig = _ensure_engines()

    results = analyzer.analyze(text=text, language="en")
    if not results:
        return text, {}

    operators = {
        "BR_CPF": OperatorConfig("replace", {"new_value": "<CPF_ANONIMIZADO>"}),
        "BR_CNPJ": OperatorConfig("replace", {"new_value": "<CNPJ_ANONIMIZADO>"}),
        "BR_PHONE": OperatorConfig("replace", {"new_value": "<TELEFONE>"}),
        "BR_EMAIL": OperatorConfig("replace", {"new_value": "<EMAIL>"}),
        "PERSON": OperatorConfig("replace", {"new_value": "<PESSOA>"}),
        "LOCATION": OperatorConfig("replace", {"new_value": "<LOCAL>"}),
        "DEFAULT": OperatorConfig("replace", {"new_value": "<PII>"}),
    }

    anonymized = anonymizer.anonymize(text=text, analyzer_results=results, operators=operators)

    counts: dict[str, int] = {}
    for result in results:
        counts[result.entity_type] = counts.get(result.entity_type, 0) + 1

    return anonymized.text, counts
