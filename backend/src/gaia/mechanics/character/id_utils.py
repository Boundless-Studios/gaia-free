"""Shared helpers for generating and normalizing character identifiers."""

from __future__ import annotations

import re
import uuid
from typing import Iterable, Optional, Set

NPC_PREFIX = "npc:"
PC_PREFIX = "pc:"
NPC_PROFILE_PREFIX = "npc_profile:"

_CLEANUP_PATTERN = re.compile(r"[^a-z0-9_]+")
_WHITESPACE_PATTERN = re.compile(r"\s+")


def slugify(value: Optional[str]) -> str:
    """Return a lowercase slug suitable for identifier construction."""
    if not value:
        return ""
    slug = str(value).strip().lower()
    slug = (
        slug.replace(" ", "_")
        .replace("-", "_")
        .replace("'", "")
        .replace('"', "")
        .replace(".", "")
        .replace(",", "")
    )
    slug = _CLEANUP_PATTERN.sub("", slug)
    slug = re.sub(r"_+", "_", slug)
    return slug.strip("_")


def normalize_identifier(identifier: Optional[str]) -> str:
    """Normalize an identifier or name for loose comparisons."""
    if not identifier:
        return ""
    normalized = str(identifier).strip().lower()
    for prefix in (NPC_PREFIX, PC_PREFIX, NPC_PROFILE_PREFIX):
        if normalized.startswith(prefix):
            normalized = normalized.split(":", 1)[1]
            break
    normalized = normalized.replace("_", " ")
    normalized = _WHITESPACE_PATTERN.sub(" ", normalized)
    return normalized.strip()


def canonicalize_identifier(candidate: Optional[str], *, default_prefix: str = NPC_PREFIX) -> str:
    """Return a canonical identifier, preserving PC prefixes when present."""
    if not candidate:
        return ""
    text = str(candidate).strip()
    lowered = text.lower()

    if lowered.startswith(NPC_PROFILE_PREFIX):
        slug = slugify(text.split(":", 1)[1])
        return f"{NPC_PREFIX}{slug or 'npc'}"

    if lowered.startswith(NPC_PREFIX):
        slug = slugify(text.split(":", 1)[1])
        return f"{NPC_PREFIX}{slug or 'npc'}"

    if lowered.startswith(PC_PREFIX):
        slug = slugify(text.split(":", 1)[1])
        return f"{PC_PREFIX}{slug or 'pc'}"

    prefix = default_prefix if default_prefix.endswith(":") else f"{default_prefix}:"
    slug = slugify(text)
    return f"{prefix}{slug or 'character'}"


def _as_identifier_set(existing_ids: Optional[Iterable[str]]) -> Set[str]:
    if not existing_ids:
        return set()
    return {str(identifier) for identifier in existing_ids if identifier}


def allocate_character_id(
    name: Optional[str],
    *,
    prefix: str,
    existing_ids: Optional[Iterable[str]] = None,
) -> str:
    """Create a unique identifier using the supplied prefix and name."""
    prefix_value = prefix if prefix.endswith(":") else f"{prefix}:"
    slug = slugify(name) or "character"
    base_id = f"{prefix_value}{slug}"

    existing = _as_identifier_set(existing_ids)
    candidate = base_id
    while candidate in existing:
        candidate = f"{base_id}_{uuid.uuid4().hex[:8]}"
    return candidate


def infer_prefix_from_role(role: Optional[str]) -> str:
    """Infer npc:/pc: prefix from a role hint."""
    if not role:
        return NPC_PREFIX
    lowered = str(role).strip().lower()
    if lowered.startswith(("pc", "player")):
        return PC_PREFIX
    return NPC_PREFIX

