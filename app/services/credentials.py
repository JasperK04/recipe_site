from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from flask import current_app

from app import db
from app.models import Credential


@dataclass(frozen=True)
class CredentialPolicy:
    lifetime_config: str
    default_lifetime: int
    lifetime_unit: str
    max_uses: int = 1
    admin_visible: bool = False


CREDENTIAL_POLICIES = {
    "password_reset": CredentialPolicy(
        lifetime_config="PASSWORD_RESET_TOKEN_LIFETIME_MINUTES",
        default_lifetime=15,
        lifetime_unit="minutes",
    ),
    "registration_invitation": CredentialPolicy(
        lifetime_config="REGISTRATION_OTC_LIFETIME_HOURS",
        default_lifetime=24,
        lifetime_unit="hours",
        admin_visible=True,
    ),
}


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_credential_policy(purpose: str) -> CredentialPolicy:
    try:
        return CREDENTIAL_POLICIES[purpose]
    except KeyError as error:
        raise ValueError(f"Unknown credential purpose: {purpose}") from error


def issue_credential(
    *,
    purpose: str,
    subject_type: str,
    subject_id: int | None = None,
    created_by_id: int | None = None,
    lifetime: int | None = None,
    max_uses: int | None = None,
    metadata: dict | None = None,
    secret: str | None = None,
) -> tuple[Credential, str]:
    policy = get_credential_policy(purpose)
    configured_lifetime = int(
        current_app.config.get(policy.lifetime_config, policy.default_lifetime)
    )
    lifetime = max(1, lifetime if lifetime is not None else configured_lifetime)
    max_uses = max(1, max_uses if max_uses is not None else policy.max_uses)
    token = secret or secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    if policy.lifetime_unit == "hours":
        expires_at = now + timedelta(hours=lifetime)
    else:
        expires_at = now + timedelta(minutes=lifetime)

    credential = Credential(
        purpose=purpose,
        secret_hash=_token_digest(token),
        subject_type=subject_type,
        subject_id=subject_id,
        created_by_id=created_by_id,
        created_at=now,
        expires_at=expires_at,
        max_uses=max_uses,
        metadata_json=metadata,
    )
    db.session.add(credential)
    db.session.flush()
    return credential, token


def find_usable_credential(*, purpose: str, token: str | None) -> Credential | None:
    if not token or len(token) > 512:
        return None
    credential = Credential.query.filter_by(
        purpose=purpose, secret_hash=_token_digest(token)
    ).first()
    if not credential or not credential.is_usable():
        return None
    return credential


def revoke_active_credentials(
    *, purpose: str, subject_type: str, subject_id: int
) -> int:
    return Credential.query.filter(
        Credential.purpose == purpose,
        Credential.subject_type == subject_type,
        Credential.subject_id == subject_id,
        Credential.used_at.is_(None),
        Credential.revoked_at.is_(None),
    ).update({Credential.revoked_at: datetime.now(UTC)}, synchronize_session=False)


def claim_credential(credential: Credential) -> bool:
    now = datetime.now(UTC)
    claimed = Credential.query.filter(
        Credential.id == credential.id,
        Credential.used_at.is_(None),
        Credential.revoked_at.is_(None),
        Credential.use_count < Credential.max_uses,
        Credential.expires_at > now,
    ).update(
        {
            Credential.used_at: now,
            Credential.use_count: Credential.use_count + 1,
        },
        synchronize_session=False,
    )
    return claimed == 1


def cleanup_expired_credentials() -> int:
    removed = Credential.query.filter(
        Credential.expires_at <= datetime.now(UTC)
    ).delete(synchronize_session=False)
    if removed:
        db.session.commit()
    return removed
