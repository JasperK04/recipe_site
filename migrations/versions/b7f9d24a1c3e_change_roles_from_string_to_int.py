"""change_roles_from_string_to_int

Revision ID: b7f9d24a1c3e
Revises: 83a2830f5168
Create Date: 2026-06-13 22:59:10.409190

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7f9d24a1c3e'
down_revision = '83a2830f5168'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("role_level", sa.Integer(), nullable=False, server_default="1")
    )

    connection = op.get_bind()

    connection.execute(sa.text("""
        UPDATE "users"
        SET role_level =
            CASE role
                WHEN 'reviewer' THEN 1
                WHEN 'creator' THEN 2
                WHEN 'admin' THEN 6
                ELSE 1
            END
    """))

    connection.execute(sa.text("""
        DROP INDEX IF EXISTS ix_users_role
    """))

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
        batch_op.alter_column(
            "role_level",
            new_column_name="role"
        )


def downgrade():
    op.add_column(
        "users",
        sa.Column("role_string", sa.String(20), nullable=False)
    )

    connection = op.get_bind()

    connection.execute(sa.text("""
        UPDATE "users"
        SET role_string =
            CASE role
                WHEN 1 THEN 'reviewer'
                WHEN 2 THEN 'creator'
                WHEN 3 THEN 'creator'
                WHEN 4 THEN 'creator'
                WHEN 5 THEN 'creator'
                WHEN 6 THEN 'admin'
                ELSE 'reviewer'
            END
    """))

    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("role")
        batch_op.alter_column(
            "role_string",
            new_column_name="role"
        )
