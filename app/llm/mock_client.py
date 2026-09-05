"""Deterministic mock chat client — implements BaseChatClient with regex/
keyword heuristics instead of a real model, dispatched by a marker phrase
in each agent's instructions."""
from __future__ import annotations

import json
import re
from collections.abc import Sequence
from datetime import UTC, date, datetime, timedelta

from agent_framework import BaseChatClient, ChatResponse, ChatResponseUpdate, Message
from dateutil import parser as date_parser

_MONTHS = (
    "January|February|March|April|May|June|July|August|September|October|November|December"
)
_DATE_RE = re.compile(
    rf"\b(\d{{1,2}}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?:{_MONTHS}),?\s+\d{{4}}"
    rf"|(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}"
    rf"|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
_NOTICE_DAYS_RE = re.compile(r"(\d+)\s*\)?\s*-?\s*days?", re.IGNORECASE)

CLAUSE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Payment Terms": ("payment terms", "payment schedule"),
    "Termination": ("termination",),
    "Renewal": ("renewal", "renew "),
    "Liability": ("liability",),
    "Indemnification": ("indemnif",),
    "Confidentiality": ("confidential",),
    "Data Protection": ("data protection", "gdpr", "personal data"),
    "Intellectual Property": ("intellectual property",),
    "Non-compete": ("non-compete", "noncompete"),
    "Non-solicitation": ("non-solicitation", "nonsolicitation"),
    "Governing Law": ("governing law",),
    "Dispute Resolution": ("dispute resolution", "arbitration"),
    "Insurance": ("insurance",),
    "Audit Rights": ("audit rights", "right to audit"),
    "Force Majeure": ("force majeure",),
}

CONTRACT_TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "Vendor Agreement": ("vendor agreement", "vendor"),
    "Employment Contract": ("employment agreement", "employment contract"),
    "NDA": ("non-disclosure agreement", "nda", "confidentiality agreement"),
    "Service Agreement": ("service agreement", "services agreement"),
    "Partnership Agreement": ("partnership agreement",),
    "Lease Agreement": ("lease agreement", "lease"),
    "Client Contract": ("client agreement", "client contract"),
}


def _find_dates(text: str) -> list[date]:
    found: list[date] = []
    for match in _DATE_RE.finditer(text):
        candidate = re.sub(r"\s+day\s+of\s+", " ", match.group(1), flags=re.IGNORECASE)
        try:
            parsed = date_parser.parse(candidate, fuzzy=False).date()
        except (ValueError, OverflowError):
            continue
        if parsed not in found:
            found.append(parsed)
    return found


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _sentence_containing(text: str, keyword: str) -> str | None:
    normalized = _normalize_whitespace(text)
    for sentence in normalized.split("."):
        if keyword.lower() in sentence.lower():
            return sentence
    return None


def _date_near_keyword(text: str, keyword: str) -> date | None:
    sentence = _sentence_containing(text, keyword)
    if sentence is None:
        return None
    dates = _find_dates(sentence)
    return dates[0] if dates else None


def _notice_period_days(text: str) -> int | None:
    sentence = _sentence_containing(text, "notice")
    if sentence is None:
        return None
    match = _NOTICE_DAYS_RE.search(sentence)
    return int(match.group(1)) if match else None


def _mock_intake(text: str) -> dict:
    lower = text.lower()
    contract_type = "General Agreement"
    for label, keywords in CONTRACT_TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            contract_type = label
            break

    parties: list[str] = []
    between_match = re.search(
        r"between\s+(.+?)\s+and\s+(.+?)[.,]", _normalize_whitespace(text), re.IGNORECASE
    )
    if between_match:
        parties = [between_match.group(1).strip(), between_match.group(2).strip()]

    effective = _first_date_near_any_keyword(text, _EFFECTIVE_KEYWORDS)
    if not effective:
        dates = _find_dates(text)
        effective = dates[0] if dates else None

    return {
        "contract_type": contract_type,
        "parties": parties,
        "effective_date": effective.isoformat() if effective else None,
    }


_HEADING_RE = re.compile(r"\b(\d{1,3})\.\s+(?=[A-Z])")
_MAX_CLAUSE_LENGTH = 3000


def _paragraph_containing(text: str, index: int) -> str:
    headings = [m.start() for m in _HEADING_RE.finditer(text)]
    earlier = [h for h in headings if h <= index]
    later = [h for h in headings if h > index]
    if earlier and (later[0] if later else len(text)) - earlier[-1] <= _MAX_CLAUSE_LENGTH:
        return text[earlier[-1] : (later[0] if later else len(text))].strip()

    start = text.rfind(".", max(0, index - _MAX_CLAUSE_LENGTH), index)
    start = start + 1 if start != -1 else max(0, index - _MAX_CLAUSE_LENGTH // 2)
    end = text.find(".", index, index + _MAX_CLAUSE_LENGTH)
    end = end + 1 if end != -1 else min(len(text), index + _MAX_CLAUSE_LENGTH // 2)
    return text[start:end].strip()


def _mock_clause(text: str) -> dict:
    normalized = _normalize_whitespace(text)
    lower = normalized.lower()
    clauses = []
    for clause_type, keywords in CLAUSE_KEYWORDS.items():
        for kw in keywords:
            idx = lower.find(kw)
            if idx == -1:
                continue
            clauses.append(
                {
                    "clause_type": clause_type,
                    "text": _paragraph_containing(normalized, idx),
                    "page_number": None,
                    "confidence": 0.8,
                }
            )
            break
    return {"clauses": clauses}


_RISK_SIGNALS: tuple[tuple[str, str, str, str], ...] = (
    (
        "unlimited liability",
        "Liability",
        "CRITICAL",
        "The contract contains an unlimited liability obligation.",
    ),
    (
        "uncapped liability",
        "Liability",
        "CRITICAL",
        "The contract contains an uncapped liability obligation.",
    ),
    (
        "broad indemnification",
        "Indemnification",
        "HIGH",
        "Indemnification obligations are broad and not mutual.",
    ),
    (
        "sole discretion",
        "Governance",
        "HIGH",
        "A party retains unilateral discretion over a material term.",
    ),
    ("automatic renewal", "Renewal", "MEDIUM", "The contract auto-renews unless notice is given."),
    ("auto-renew", "Renewal", "MEDIUM", "The contract auto-renews unless notice is given."),
    ("non-compete", "Non-compete", "MEDIUM", "A non-compete restriction is present."),
)
_SEVERITY_SCORE = {"CRITICAL": 90, "HIGH": 72, "MEDIUM": 45, "LOW": 20}


def _mock_risk(text: str) -> dict:
    lower = text.lower()
    risks = []
    for phrase, clause_type, severity, reason in _RISK_SIGNALS:
        if phrase in lower:
            risks.append(
                {
                    "risk_type": clause_type,
                    "clause_type": clause_type,
                    "severity": severity,
                    "score": _SEVERITY_SCORE[severity],
                    "reason": reason,
                    "recommendation": f"Request lawyer review of the {clause_type.lower()} terms.",
                    "confidence": 0.85,
                }
            )
    if not risks:
        risks.append(
            {
                "risk_type": "General",
                "clause_type": None,
                "severity": "LOW",
                "score": _SEVERITY_SCORE["LOW"],
                "reason": "No high-risk phrasing detected by baseline screening.",
                "recommendation": "Standard review recommended.",
                "confidence": 0.6,
            }
        )
    return {"risks": risks}


_EFFECTIVE_KEYWORDS = ("effective date", "effective", "commencement date", "commence")
_EXPIRY_KEYWORDS = (
    "expiration date",
    "expir",
    "termination date",
    "valid until",
    "valid through",
    "term of this agreement",
    "end date",
)
_RENEWAL_KEYWORDS = ("renewal date", "renewal", "renews")

_DURATION_RE = re.compile(r"(?:period|term)\s+of\s+(?:\w+\s+)?\(?(\d+)\)?\s*(year|month)s?", re.IGNORECASE)


def _first_date_near_any_keyword(text: str, keywords: tuple[str, ...]) -> date | None:
    for keyword in keywords:
        found = _date_near_keyword(text, keyword)
        if found:
            return found
    return None


def _duration_from_effective(text: str, effective: date) -> date | None:
    match = _DURATION_RE.search(_normalize_whitespace(text))
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2).lower()
    if unit == "year":
        return effective.replace(year=effective.year + amount)
    month_index = effective.month - 1 + amount
    year = effective.year + month_index // 12
    month = month_index % 12 + 1
    day = min(effective.day, 28)
    return effective.replace(year=year, month=month, day=day)


def _mock_deadline(text: str) -> dict:
    deadlines = []
    effective = _first_date_near_any_keyword(text, _EFFECTIVE_KEYWORDS)
    if effective:
        deadlines.append(
            {"deadline_type": "effective_date", "date": effective.isoformat(), "notice_period_days": None}
        )

    expiry = _first_date_near_any_keyword(text, _EXPIRY_KEYWORDS)
    if not expiry and effective:
        expiry = _duration_from_effective(text, effective)
    if expiry:
        deadlines.append(
            {"deadline_type": "expiry_date", "date": expiry.isoformat(), "notice_period_days": None}
        )

    notice_days = _notice_period_days(text)
    if expiry and notice_days:
        notice_date = expiry - timedelta(days=notice_days)
        deadlines.append(
            {
                "deadline_type": "termination_notice",
                "date": notice_date.isoformat(),
                "notice_period_days": notice_days,
            }
        )

    renewal = _first_date_near_any_keyword(text, _RENEWAL_KEYWORDS)
    if renewal:
        deadlines.append(
            {"deadline_type": "renewal_date", "date": renewal.isoformat(), "notice_period_days": None}
        )

    return {"deadlines": deadlines}


def _mock_compliance(text: str) -> dict:
    found_text = re.search(r"CLAUSES_FOUND:\s*(.*)", text).group(1)
    found = {c.strip().lower() for c in found_text.split(",") if c.strip()}

    required_text = re.search(r"REQUIRED_CLAUSES:\s*(.*)", text).group(1)
    required = [r.strip() for r in required_text.split(",") if r.strip()]

    results = [{"requirement": req, "satisfied": req.lower() in found} for req in required]
    violations = [r["requirement"] for r in results if not r["satisfied"]]
    score = 100.0 * (len(results) - len(violations)) / len(results) if results else 100.0

    return {"results": results, "violations": violations, "score": round(score, 1)}


_DISPATCH: tuple[tuple[str, callable], ...] = (
    ("Intake Agent", _mock_intake),
    ("Clause Extraction Agent", _mock_clause),
    ("Risk Analysis Agent", _mock_risk),
    ("Deadline Agent", _mock_deadline),
    ("Compliance Agent", _mock_compliance),
)


class MockChatClient(BaseChatClient):
    OTEL_PROVIDER_NAME = "mock"

    async def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options, **kwargs
    ):
        # Marker-bearing instructions arrive via options["instructions"],
        # not messages (agent_framework.Agent).
        instructions = (options or {}).get("instructions", "") if hasattr(options, "get") else ""
        prompt_text = "\n".join(m.text for m in messages if m.text)

        payload: dict = {"note": "no matching mock agent handler found"}
        for marker, handler in _DISPATCH:
            if marker in instructions:
                payload = handler(prompt_text)
                break

        reply_text = json.dumps(payload)

        if stream:

            async def _stream():
                yield ChatResponseUpdate(role="assistant", contents=[{"type": "text", "text": reply_text}])

            return _stream()

        return ChatResponse(
            messages=[Message(role="assistant", contents=[reply_text])],
            response_id=f"mock-{datetime.now(UTC).timestamp():.0f}",
            model="mock-heuristic-v1",
        )
