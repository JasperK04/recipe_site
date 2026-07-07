from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping
from functools import lru_cache
from dataclasses import asdict, dataclass
from typing import Literal

import spacy

ModerationStatus = Literal["allowed", "flagged"]


@dataclass(slots=True)
class ModerationRule:
    """Single text-match rule used by the moderation engine."""

    category: str
    term: str
    message: str
    pattern: re.Pattern[str]


@dataclass(slots=True)
class ModerationIssue:
    """A single moderation hit."""

    field: str
    category: str
    term: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(slots=True)
class ModerationResult:
    """Outcome of a moderation scan."""

    status: ModerationStatus
    issues: list[ModerationIssue]

    @property
    def is_flagged(self) -> bool:
        return self.status == "flagged"

    @property
    def messages(self) -> list[str]:
        return [issue.message for issue in self.issues]

    def format_messages(self, *, prefix: str | None = None) -> str:
        messages = self.messages
        if not messages:
            return ""
        if prefix:
            return prefix + " " + "; ".join(messages)
        return "; ".join(messages)


MODERATION_ENABLED = True


def _is_moderation_enabled() -> bool:
    try:
        from flask import current_app

        return bool(current_app.config.get("MODERATION_ENABLED", MODERATION_ENABLED))
    except Exception:
        return MODERATION_ENABLED


@lru_cache(maxsize=1)
def _spacy_model():
    try:
        return spacy.load("nl_core_news_sm", exclude=["parser", "ner"])
    except Exception:
        return None


def _compile_term_pattern(term: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in term.split() if part]
    if not parts:
        raise ValueError("Moderation term cannot be empty")
    body = r"[\W_]+".join(parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])", re.IGNORECASE)


def _rule(category: str, term: str, message: str) -> ModerationRule:
    return ModerationRule(
        category=category,
        term=term,
        message=message,
        pattern=_compile_term_pattern(term),
    )


MODERATION_RULES: tuple[ModerationRule, ...] = (
    # NSFW / sexual content
    _rule("nsfw", "porn", 'Bevat mogelijk NSFW-content: "porn".'),
    _rule("nsfw", "porno", 'Bevat mogelijk NSFW-content: "porno".'),
    _rule("nsfw", "xxx", 'Bevat mogelijk NSFW-content: "xxx".'),
    _rule("nsfw", "onlyfans", 'Bevat mogelijk NSFW-content: "onlyfans".'),
    _rule("nsfw", "sexual", 'Bevat mogelijk NSFW-content: "sexual".'),
    _rule("nsfw", "seks", 'Bevat mogelijk NSFW-content: "seks".'),
    _rule("nsfw", "sex", 'Bevat mogelijk NSFW-content: "sex".'),
    _rule("nsfw", "sexy", 'Bevat mogelijk NSFW-content: "sexy".'),
    _rule("nsfw", "blowjob", 'Bevat mogelijk NSFW-content: "blowjob".'),
    _rule("nsfw", "handjob", 'Bevat mogelijk NSFW-content: "handjob".'),
    _rule("nsfw", "boobs", 'Bevat mogelijk NSFW-content: "boobs".'),
    _rule("nsfw", "dick", 'Bevat mogelijk NSFW-content: "dick".'),
    _rule("nsfw", "pussy", 'Bevat mogelijk NSFW-content: "pussy".'),
    _rule("nsfw", "cock", 'Bevat mogelijk NSFW-content: "cock".'),
    _rule("nsfw", "cum", 'Bevat mogelijk NSFW-content: "cum".'),
    _rule("nsfw", "neuken", 'Bevat mogelijk NSFW-content: "neuken".'),
    _rule("nsfw", "lul", 'Bevat mogelijk NSFW-content: "lul".'),
    _rule("nsfw", "kut", 'Bevat mogelijk NSFW-content: "kut".'),
    _rule("nsfw", "hoer", 'Bevat mogelijk NSFW-content: "hoer".'),
    _rule("nsfw", "slet", 'Bevat mogelijk NSFW-content: "slet".'),
    _rule("nsfw", "piemel", 'Bevat mogelijk NSFW-content: "piemel".'),
    _rule("nsfw", "penis", 'Bevat mogelijk NSFW-content: "penis".'),
    _rule("nsfw", "vagina", 'Bevat mogelijk NSFW-content: "vagina".'),
    _rule("nsfw", "kont", 'Bevat mogelijk NSFW-content: "kont".'),
    _rule("nsfw", "sexshop", 'Bevat mogelijk NSFW-content: "sexshop".'),
    _rule("nsfw", "erotisch", 'Bevat mogelijk NSFW-content: "erotisch".'),
    _rule("nsfw", "erotiek", 'Bevat mogelijk NSFW-content: "erotiek".'),

    # General profanity / insults
    _rule("profanity", "fuck", 'Bevat aanstootgevende taal: "fuck".'),
    _rule("profanity", "shit", 'Bevat aanstootgevende taal: "shit".'),
    _rule("profanity", "bitch", 'Bevat aanstootgevende taal: "bitch".'),
    _rule("profanity", "asshole", 'Bevat aanstootgevende taal: "asshole".'),
    _rule("profanity", "bastard", 'Bevat aanstootgevende taal: "bastard".'),
    _rule("profanity", "moron", 'Bevat aanstootgevende taal: "moron".'),
    _rule("profanity", "idiot", 'Bevat aanstootgevende taal: "idiot".'),
    _rule("profanity", "stupid", 'Bevat aanstootgevende taal: "stupid".'),
    _rule("profanity", "cunt", 'Bevat aanstootgevende taal: "cunt".'),
    _rule("profanity", "slut", 'Bevat aanstootgevende taal: "slut".'),
    _rule("profanity", "whore", 'Bevat aanstootgevende taal: "whore".'),
    _rule("profanity", "klootzak", 'Bevat aanstootgevende taal: "klootzak".'),
    _rule("profanity", "eikel", 'Bevat aanstootgevende taal: "eikel".'),
    _rule("profanity", "idioot", 'Bevat aanstootgevende taal: "idioot".'),
    _rule("profanity", "debiel", 'Bevat aanstootgevende taal: "debiel".'),
    _rule("profanity", "trut", 'Bevat aanstootgevende taal: "trut".'),
    _rule("profanity", "tering", 'Bevat aanstootgevende taal: "tering".'),
    _rule("profanity", "tyfus", 'Bevat aanstootgevende taal: "tyfus".'),
    _rule("profanity", "godverdomme", 'Bevat aanstootgevende taal: "godverdomme".'),
    _rule("profanity", "kanker", 'Bevat aanstootgevende taal: "kanker".'),
)


def _flatten_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, Iterable) and not isinstance(value, (bytes, bytearray)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", _flatten_text(value))
    return " ".join(text.casefold().split())


def _lemmatize_text(value: object) -> str:
    text = _normalize_text(value)
    if not text:
        return ""

    nlp = _spacy_model()
    if nlp is None:
        return text

    doc = nlp(text)
    lemmas: list[str] = []
    for token in doc:
        if token.is_space or token.is_punct:
            continue
        lemma = token.lemma_.casefold().strip()
        if not lemma or lemma == "-pron-":
            lemma = token.text.casefold().strip()
        if lemma:
            lemmas.append(lemma)
    return " ".join(lemmas)


def moderate_texts(fields: Mapping[str, object]) -> ModerationResult:
    """Scan all provided fields and return every matching moderation issue."""
    if not _is_moderation_enabled():
        return ModerationResult(status="allowed", issues=[])

    issues: list[ModerationIssue] = []
    seen: set[tuple[str, str, str]] = set()

    for field_name, raw_value in fields.items():
        normalized = _normalize_text(raw_value)
        if not normalized:
            continue
        lemmatized = _lemmatize_text(normalized)

        for rule in MODERATION_RULES:
            if not rule.pattern.search(normalized) and not rule.pattern.search(
                lemmatized
            ):
                continue

            key = (field_name, rule.category, rule.term)
            if key in seen:
                continue
            seen.add(key)
            issues.append(
                ModerationIssue(
                    field=field_name,
                    category=rule.category,
                    term=rule.term,
                    message=f"{field_name}: {rule.message}",
                )
            )

    return ModerationResult(
        status="flagged" if issues else "allowed",
        issues=issues,
    )


def moderate_username(username: str | None) -> ModerationResult:
    return moderate_texts({"username": username})


def moderate_recipe_payload(
    *,
    title: object = None,
    description: object = None,
    ingredients: object = None,
    instructions: object = None,
) -> ModerationResult:
    return moderate_texts(
        {
            "title": title,
            "description": description,
            "ingredients": ingredients,
            "instructions": instructions,
        }
    )
