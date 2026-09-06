"""Move one-time credentials into a purpose-aware credentials table.

Revision ID: f1a2b3c4d5e6
Revises: e4f6a8b0c2d4
Create Date: 2026-09-06 00:00:00.000000
"""

import hashlib

import sqlalchemy as sa
from alembic import op


revision = "f1a2b3c4d5e6"
down_revision = "e4f6a8b0c2d4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "credentials",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("purpose", sa.String(length=80), nullable=False),
        sa.Column("secret_hash", sa.String(length=128), nullable=False),
        sa.Column("subject_type", sa.String(length=40), nullable=False),
        sa.Column("subject_id", sa.Integer(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column("use_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_uses", sa.Integer(), server_default="1", nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["subject_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_hash"),
    )
    op.create_index("ix_credentials_purpose", "credentials", ["purpose"], unique=False)
    op.create_index(
        "ix_credentials_purpose_expires_at",
        "credentials",
        ["purpose", "expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_credentials_secret_hash", "credentials", ["secret_hash"], unique=False
    )
    op.create_index(
        "ix_credentials_subject", "credentials", ["subject_type", "subject_id"], unique=False
    )

    # Preserve legacy secrets by hashing the values while they are still available.
    connection = op.get_bind()
    legacy_rows = connection.execute(
        sa.text(
            """
            SELECT code, purpose, token_hash, user_id, created_at, expires_at, used_at
            FROM otc
            """
        )
    ).mappings()
    for row in legacy_rows:
        if row["token_hash"]:
            purpose = "password_reset"
            secret_hash = row["token_hash"]
            subject_type = "user"
            subject_id = row["user_id"]
            use_count = 1 if row["used_at"] else 0
        else:
            purpose = "registration_invitation"
            secret_hash = hashlib.sha256(row["code"].encode("utf-8")).hexdigest()
            subject_type = "registration"
            subject_id = None
            use_count = 0
        connection.execute(
            sa.text(
                """
                INSERT INTO credentials (
                    purpose, secret_hash, subject_type, subject_id, created_at,
                    expires_at, used_at, max_uses, use_count, metadata_json
                ) VALUES (
                    :purpose, :secret_hash, :subject_type, :subject_id, :created_at,
                    :expires_at, :used_at, 1, :use_count, :metadata_json
                )
                """
            ),
            {
                "purpose": purpose,
                "secret_hash": secret_hash,
                "subject_type": subject_type,
                "subject_id": subject_id,
                "created_at": row["created_at"],
                "expires_at": row["expires_at"],
                "used_at": row["used_at"],
                "use_count": use_count,
                "metadata_json": None,
            },
        )

    op.drop_table("otc")


def downgrade():
    # Reset secrets cannot be safely reconstructed from hashes during downgrade.
    # The credential table is therefore intentionally not copied back into OTC.
    op.drop_index("ix_credentials_subject", table_name="credentials")
    op.drop_index("ix_credentials_secret_hash", table_name="credentials")
    op.drop_index("ix_credentials_purpose_expires_at", table_name="credentials")
    op.drop_index("ix_credentials_purpose", table_name="credentials")
    op.drop_table("credentials")
    op.create_table(
        "otc",
        sa.Column("code", sa.String(length=8), nullable=False),
        sa.Column("purpose", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("used_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("code"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_otc_expires_at", "otc", ["expires_at"], unique=False)
    op.create_index("ix_otc_token_hash", "otc", ["token_hash"], unique=True)
    op.create_index("ix_otc_user_id", "otc", ["user_id"], unique=False)
