from __future__ import annotations

from datetime import datetime, timezone

from app import db


class OTC(db.Model):
    __tablename__ = "otc"
    __table_args__ = (db.Index("ix_otc_expires_at", "expires_at"),)

    code = db.Column(db.String(8), primary_key=True, unique=True, nullable=False)
    purpose = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime, nullable=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def is_expired(self):
        return datetime.now(timezone.utc) >= self.expires_at

    def __repr__(self):
        return f"<OTC code={self.code} expires_at={self.expires_at}>"
