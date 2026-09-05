"""Deterministic mock chat client.

No API key, no network call, no real language understanding — this exists
so the whole agent pipeline (intake -> clause -> risk -> deadline ->
compliance) runs and is testable with zero cost. It implements exactly
the extension point `agent_framework.BaseChatClient` documents
(`_inner_get_response`), so from every agent's point of view this is an
ordinary chat client; swapping in a real provider later means adding a
branch in `llm/client.py`, not touching agent code.

Dispatch works by looking for a marker phrase in the agent's own system
instructions (each agent module sets `instructions=...` containing e.g.
"Clause Extraction Agent" — see agents/*.py) combined with structured
markers each agent embeds in its prompt (e.g. "CLAUSES_FOUND: ..."). Each
`_mock_*` function below returns the exact JSON shape the matching real
agent module expects to parse.
"""
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
    # "1st day of January, 2026" / "1st January 2026" — the "day of" is
    # the common formal-legal phrasing ("...entered into as of the Nth
    # day of Month, YYYY"), left optional so the plainer form still matches.
    rf"\b(\d{{1,2}}(?:st|nd|rd|th)?\s+(?:day\s+of\s+)?(?:{_MONTHS}),?\s+\d{{4}}"
    rf"|(?:{_MONTHS})\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}"
    rf"|\d{{1,2}}[/-]\d{{1,2}}[/-]\d{{2,4}}"
    rf"|\d{{4}}-\d{{2}}-\d{{2}})\b",
    re.IGNORECASE,
)
# "90 days", "ninety (90) days" — the closing paren between a spelled-out
# number and its numeral is common in legal drafting.
_NOTICE_DAYS_RE = re.compile(r"(\d+)\s*\)?\s*-?\s*days?", re.IGNORECASE)

# clause_type -> keyword(s) that signal its presence in contract text.
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
        # "day of" is only in the regex to *match* formal phrasing ("the
        # 1st day of January, 2026") — dateutil's strict (fuzzy=False)
        # parser doesn't know those words, so strip them before parsing.
        candidate = re.sub(r"\s+day\s+of\s+", " ", match.group(1), flags=re.IGNORECASE)
        try:
            parsed = date_parser.parse(candidate, fuzzy=False).date()
        except (ValueError, OverflowError):
            continue
        if parsed not in found:
            found.append(parsed)
    return found


def _normalize_whitespace(text: str) -> str:
    """Collapse every run of whitespace (including newlines) to a single
    space. PDF text extraction (pypdf) emits one `\\n` per *rendered
    line*, not per sentence, so a real contract routinely wraps
    "...effective as of\\nJanuary 1, 2026..." across two lines — treating
    `\\n` as a sentence boundary (as a naive split would) then separates
    a keyword from the date right next to it. Sentences are still
    delimited by `.` after this, which line-wrapping never removes."""
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

    # Normalized so a PDF line-wrap between the party names (or before the
    # trailing punctuation) doesn't break the match — same reasoning as
    # _sentence_containing.
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


# A numbered section heading — "12. Insurance and Indemnification. ..." —
# is a strong, common signal for where one clause ends and the next
# begins in real contracts (unlike a fixed character window, which lands
# mid-word as often as not).
_HEADING_RE = re.compile(r"\b(\d{1,3})\.\s+(?=[A-Z])")
_MAX_CLAUSE_LENGTH = 3000  # guards against a runaway match on unnumbered text


def _paragraph_containing(text: str, index: int) -> str:
    """The complete clause/paragraph around character `index` of
    (whitespace-normalized) `text` — evidence a lawyer can actually read,
    not a fixed-width snippet that starts and ends mid-word. Prefers
    numbered-heading boundaries; falls back to the enclosing sentence for
    text that isn't numbered, capped so neither can swallow half the
    document."""
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


# Phrases that push a clause into a specific risk severity. Checked in
# order; the first match wins. This is a deliberately small, explainable
# rule set — a real model would reason about the clause instead.
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


# Keyword variants tried in order for each deadline type — real contracts
# phrase these many ways; the first one that has a date in its sentence
# wins. Broader/riskier phrases (e.g. bare "terminat") are deliberately
# left out in favor of specific compounds ("termination date") to keep
# false positives low.
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
    """Contracts often state a term length instead of an explicit expiry
    date ("...for a period of three (3) years from the Effective Date").
    Only used as a fallback when no explicit expiry date was found."""
    match = _DURATION_RE.search(_normalize_whitespace(text))
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2).lower()
    if unit == "year":
        return effective.replace(year=effective.year + amount)
    # Month arithmetic without a dependency: normalize month overflow by
    # hand rather than pulling in dateutil.relativedelta for one call site.
    month_index = effective.month - 1 + amount
    year = effective.year + month_index // 12
    month = month_index % 12 + 1
    day = min(effective.day, 28)  # side-steps day-31-in-February-style overflow
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
    # compliance_agent.py always emits both literal prefixes (even with
    # empty lists — `', '.join([])` is just ""), so both matches are
    # guaranteed; the `.strip()` filters keep an empty list from turning
    # into {""} / [""].
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
    """Zero-cost, offline stand-in for a real LLM chat client."""

    OTEL_PROVIDER_NAME = "mock"

    async def _inner_get_response(
        self, *, messages: Sequence[Message], stream: bool, options, **kwargs
    ):
        # The agent's marker-bearing system instructions arrive via
        # options["instructions"] (agent_framework.Agent), not as a
        # message — only the user prompt is in `messages`. The marker is
        # used only to pick a handler; the handler itself must run on
        # the prompt text alone; the instructions text describes dates
        # like "expiration date" that would otherwise shadow real dates
        # in the contract text.
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
