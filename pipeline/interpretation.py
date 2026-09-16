"""Deterministic, evidence-grounded interpretation of existing model output."""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Mapping

import pandas as pd


class InterpretationError(ValueError):
    pass


class ReviewStatus(StrEnum):
    RESULT_AVAILABLE = "result_available"
    NEEDS_REVIEW = "needs_review"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


@dataclass(frozen=True)
class CategoryKnowledge:
    display_name: str
    description: str
    risk_explanation: str
    actions: tuple[str, ...]


@dataclass(frozen=True)
class PublicEvidenceItem:
    feature_name: str
    display_name: str
    feature_value: object
    shap_value: float
    direction: str
    human_explanation: str
    evidence_strength: str


@dataclass(frozen=True)
class UserFacingInterpretation:
    predicted_category: str
    category_display_name: str
    short_summary: str
    malware_description: str
    risk_explanation: str
    confidence_value: float
    confidence_label: str | None
    review_status: ReviewStatus
    review_threshold_active: bool
    evidence_items: tuple[PublicEvidenceItem, ...]
    recommended_actions: tuple[str, ...]
    limitations: tuple[str, ...]
    technical_disclaimer: str


COMMON_PRECAUTIONS = (
    "If compromise is suspected, disconnect the affected device from sensitive networks.",
    "Run a scan with trusted, up-to-date endpoint security software.",
    "Preserve relevant logs and telemetry for review by an IT or security professional.",
    "Avoid entering sensitive credentials on the device until it has been reviewed.",
)


def _knowledge(display, description, risk, extra=()):
    return CategoryKnowledge(display, description, risk, tuple(extra) + COMMON_PRECAUTIONS)


CATEGORY_KNOWLEDGE: Mapping[str, CategoryKnowledge] = MappingProxyType({
    "Backdoor": _knowledge(
        "Unauthorized remote-access malware",
        "A backdoor is malware intended to provide hidden or unauthorized access to a system.",
        "The category can indicate persistent remote access, but this model result is not proof that access occurred.",
    ),
    "Benign": CategoryKnowledge(
        "No malware category identified",
        "The observed telemetry was classified as benign rather than one of BEACON's malware categories.",
        "A benign classification lowers concern for this sample but does not guarantee that the system is clean.",
        ("Continue normal security monitoring.",
         "If suspicious symptoms remain, use a trusted security scan or ask an IT professional to review the device."),
    ),
    "Exploit": _knowledge(
        "Exploit-related activity",
        "This category represents activity associated with attempts to take advantage of a software weakness.",
        "The classification does not identify a specific vulnerability or prove that exploitation succeeded.",
    ),
    "HackTool": _knowledge(
        "Potentially risky security tool",
        "This category covers tools that may be used for legitimate testing or for unauthorized activity.",
        "Context and authorization are essential because tool-like behavior is not necessarily malicious.",
    ),
    "Hoax": _knowledge(
        "Deceptive or false-threat software",
        "This category represents software intended to mislead users about a threat or system condition.",
        "The classification indicates similarity to deceptive software, not confirmation of user impact.",
    ),
    "Rootkit": _knowledge(
        "Stealth and privileged-access malware",
        "A rootkit is malware designed to hide itself or other activity while maintaining privileged access.",
        "Rootkit-like classification warrants careful review, but BEACON has not confirmed privileged compromise.",
    ),
    "Trojan": _knowledge(
        "Malware disguised as legitimate software",
        "A Trojan is malicious software presented or delivered as something legitimate.",
        "The category describes a malware family type; it does not establish how the sample arrived or what it did.",
    ),
    "Virus": _knowledge(
        "File-infecting or self-replicating malware",
        "A virus is malware capable of attaching to files or replicating when affected content runs.",
        "This result does not prove that files were modified or that replication occurred on this device.",
    ),
    "Worm": _knowledge(
        "Self-spreading malware",
        "A worm is malware capable of spreading between systems or across networks.",
        "The category does not prove that propagation occurred in the analyzed environment.",
    ),
})


FEATURE_FAMILIES = (
    (("iat", "delta_time", "duration", "active", "idle", "handshake"),
     "Timing pattern", "Connection timing patterns"),
    (("payload", "bytes", "packet", "segment", "bulk", "rate"),
     "Traffic volume pattern", "Packet and traffic-volume patterns"),
    (("port", "protocol", "conn", "listen"),
     "Connection characteristic", "Connection and service characteristics"),
    (("malfind", "inject"), "Memory injection indicator", "Memory-injection measurements"),
    (("dll", "module", "ldr"), "Loaded-code pattern", "Loaded module and library measurements"),
    (("handle", "mutant"), "System-object pattern", "Handle and system-object measurements"),
    (("process", "pslist", "nproc", "thread"),
     "Process activity pattern", "Process and thread measurements"),
    (("callback",), "Callback pattern", "System callback measurements"),
)


def _feature_translation(feature_name: str) -> tuple[str, str]:
    normalized = feature_name.lower()
    for markers, display, phrase in FEATURE_FAMILIES:
        if any(marker in normalized for marker in markers):
            return display, phrase
    return "Behavioral measurement", "A model-measured behavioral characteristic"


def _evidence_items(top_features: pd.DataFrame, limit: int = 5) -> tuple[PublicEvidenceItem, ...]:
    required = {"feature", "value", "shap_value"}
    if not required <= set(top_features.columns):
        raise InterpretationError("SHAP evidence is missing required fields.")
    ordered = top_features.assign(_magnitude=top_features["shap_value"].abs()).sort_values(
        "_magnitude", ascending=False, kind="stable"
    ).head(limit)
    items = []
    for rank, row in enumerate(ordered.itertuples(index=False), start=1):
        display, phrase = _feature_translation(row.feature)
        direction = "toward" if row.shap_value > 0 else "away" if row.shap_value < 0 else "neutral"
        if direction == "toward":
            explanation = f"{phrase} contributed toward the reported classification."
        elif direction == "away":
            explanation = f"{phrase} reduced support for the reported classification."
        else:
            explanation = f"{phrase} had no directional contribution for this explanation row."
        strength = "strongest" if rank == 1 else "strong" if rank <= 3 else "supporting"
        items.append(PublicEvidenceItem(
            feature_name=row.feature, display_name=display, feature_value=row.value,
            shap_value=float(row.shap_value), direction=direction,
            human_explanation=explanation, evidence_strength=strength,
        ))
    return tuple(items)


def interpret_analysis(result: dict, stream: str, evidence_limit: int = 5) -> UserFacingInterpretation:
    """Translate, without recalculating, one completed scientific result."""
    if not result or "verdict" not in result:
        raise InterpretationError("A completed model result is required for interpretation.")
    category = result["verdict"]
    if category not in CATEGORY_KNOWLEDGE:
        raise InterpretationError(f"Unsupported malware category: {category!r}")
    if "confidence" not in result or "top_features" not in result:
        raise InterpretationError("The model result lacks confidence or SHAP evidence.")
    confidence = float(result["confidence"])
    knowledge = CATEGORY_KNOWLEDGE[category]
    evidence = _evidence_items(result["top_features"], evidence_limit)

    limitations = [
        "This is a model classification based on the supplied telemetry, not proof of infection or compromise.",
        "No validated confidence threshold is stored for operational referral, so Needs Review is not activated automatically.",
    ]
    if stream == "memory":
        limitations.append(
            "Memory-based family classification is less reliable than Network capture-level classification in the current model."
        )
    elif stream != "network":
        raise InterpretationError(f"Unsupported analysis stream: {stream!r}")

    return UserFacingInterpretation(
        predicted_category=category,
        category_display_name=knowledge.display_name,
        short_summary=f"The model classified this {stream} telemetry as {category}.",
        malware_description=knowledge.description,
        risk_explanation=knowledge.risk_explanation,
        confidence_value=confidence,
        confidence_label=None,
        review_status=ReviewStatus.RESULT_AVAILABLE,
        review_threshold_active=False,
        evidence_items=evidence,
        recommended_actions=knowledge.actions,
        limitations=tuple(limitations),
        technical_disclaimer=(
            "Public explanations deterministically translate the existing category, probability, "
            "and SHAP evidence. They do not alter inference and do not use generative AI."
        ),
    )
