"""Move recipe images from database blobs to filesystem

Revision ID: 6d6db1c2e5f1
Revises: 5b8d1c7a9e34
Create Date: 2026-04-21 17:00:00.000000
"""

import os
import uuid
from pathlib import Path

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6d6db1c2e5f1"
down_revision = "5b8d1c7a9e34"
branch_labels = None
depends_on = None


def _recipe_image_dir() -> Path:
    project_root = Path(__file__).resolve().parents[2]
    raw_data_root = (os.getenv("DATAROOT") or "data").strip()
    data_root = Path(raw_data_root).expanduser()
    if not data_root.is_absolute():
        data_root = project_root / data_root
    recipe_dir = data_root / "recipe"
    recipe_dir.mkdir(parents=True, exist_ok=True)
    return recipe_dir


def _has_column(inspector, table_name: str, column_name: str) -> bool:
    return any(col["name"] == column_name for col in inspector.get_columns(table_name))


def _has_index(inspector, table_name: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in inspector.get_indexes(table_name))


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_image_id = _has_column(inspector, "recipes", "image_id")
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        if not has_image_id:
            batch_op.add_column(
                sa.Column("image_id", sa.String(length=64), nullable=True)
            )

    inspector = sa.inspect(bind)
    if _has_column(inspector, "recipes", "image_data"):
        recipe_dir = _recipe_image_dir()
        rows = bind.execute(
            sa.text("SELECT id, image_data FROM recipes WHERE image_data IS NOT NULL")
        ).mappings()
        for row in rows:
            image_id = uuid.uuid4().hex
            (recipe_dir / f"{image_id}.webp").write_bytes(row["image_data"])
            bind.execute(
                sa.text(
                    "UPDATE recipes SET image_id = :image_id WHERE id = :recipe_id"
                ),
                {"image_id": image_id, "recipe_id": row["id"]},
            )

    inspector = sa.inspect(bind)
    has_image_data = _has_column(inspector, "recipes", "image_data")
    has_image_mime = _has_column(inspector, "recipes", "image_mime")
    has_image_id_index = _has_index(inspector, "recipes", "ix_recipes_image_id")
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        if not has_image_id_index:
            batch_op.create_index(
                batch_op.f("ix_recipes_image_id"), ["image_id"], unique=False
            )
        if has_image_mime:
            batch_op.drop_column("image_mime")
        if has_image_data:
            batch_op.drop_column("image_data")


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    has_image_data = _has_column(inspector, "recipes", "image_data")
    has_image_mime = _has_column(inspector, "recipes", "image_mime")
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        if not has_image_data:
            batch_op.add_column(
                sa.Column("image_data", sa.LargeBinary(), nullable=True)
            )
        if not has_image_mime:
            batch_op.add_column(
                sa.Column("image_mime", sa.String(length=50), nullable=True)
            )

    inspector = sa.inspect(bind)
    if _has_column(inspector, "recipes", "image_id"):
        recipe_dir = _recipe_image_dir()
        rows = bind.execute(
            sa.text("SELECT id, image_id FROM recipes WHERE image_id IS NOT NULL")
        ).mappings()
        for row in rows:
            image_path = recipe_dir / f"{row['image_id']}.webp"
            if image_path.is_file():
                bind.execute(
                    sa.text(
                        "UPDATE recipes "
                        "SET image_data = :image_data, image_mime = 'image/webp' "
                        "WHERE id = :recipe_id"
                    ),
                    {"image_data": image_path.read_bytes(), "recipe_id": row["id"]},
                )

    inspector = sa.inspect(bind)
    has_image_id_index = _has_index(inspector, "recipes", "ix_recipes_image_id")
    has_image_id = _has_column(inspector, "recipes", "image_id")
    with op.batch_alter_table("recipes", schema=None) as batch_op:
        if has_image_id_index:
            batch_op.drop_index(batch_op.f("ix_recipes_image_id"))
        if has_image_id:
            batch_op.drop_column("image_id")
