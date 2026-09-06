from __future__ import annotations

from datetime import UTC, datetime

from app import db


class Credential(db.Model):
    __tablename__ = "credentials"
    __table_args__ = (
        db.Index("ix_credentials_purpose_expires_at", "purpose", "expires_at"),
        db.Index("ix_credentials_subject", "subject_type", "subject_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    purpose = db.Column(db.String(80), nullable=False, index=True)
    secret_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    subject_type = db.Column(db.String(40), nullable=False)
    subject_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    use_count = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    max_uses = db.Column(db.Integer, nullable=False, default=1, server_default="1")
    metadata_json = db.Column(db.JSON, nullable=True)

    subject_user = db.relationship(
        "User", foreign_keys=[subject_id], backref="credentials", lazy="joined"
    )

    def is_expired(self):
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return datetime.now(UTC) >= expires_at

    def is_usable(self):
        return (
            self.used_at is None
            and self.revoked_at is None
            and self.use_count < self.max_uses
            and not self.is_expired()
        )

    def __repr__(self):
        return f"<Credential purpose={self.purpose} id={self.id}>"
