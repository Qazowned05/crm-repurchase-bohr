"""normalize product brands and categories

Revision ID: 0011_normalize_product_catalog
Revises: 0010_typification_hierarchy
"""
from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0011_normalize_product_catalog"
down_revision: str | None = "0010_typification_hierarchy"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "brands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("name"),
    )
    op.create_index("ix_brands_name", "brands", ["name"])
    op.create_table(
        "product_categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"), sa.UniqueConstraint("name"),
    )
    op.create_index("ix_product_categories_name", "product_categories", ["name"])
    op.add_column("products", sa.Column("brand_id", sa.String(length=36), nullable=True))
    op.add_column("products", sa.Column("category_id", sa.String(length=36), nullable=True))

    connection = op.get_bind()
    brand_id = str(uuid4())
    connection.execute(sa.text("INSERT INTO brands (id, name, is_active, created_at, updated_at) VALUES (:id, 'SIN MARCA', :active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": brand_id, "active": True})
    category_ids: dict[str, str] = {}
    for category in connection.execute(sa.text("SELECT DISTINCT category FROM products")).scalars():
        name = category.strip() if category and category.strip() else "SIN CATEGORIA"
        if name not in category_ids:
            category_ids[name] = str(uuid4())
            connection.execute(sa.text("INSERT INTO product_categories (id, name, is_active, created_at, updated_at) VALUES (:id, :name, :active, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"), {"id": category_ids[name], "name": name, "active": True})
        connection.execute(sa.text("UPDATE products SET brand_id = :brand_id, category_id = :category_id WHERE category = :category"), {"brand_id": brand_id, "category_id": category_ids[name], "category": category})

    with op.batch_alter_table("products") as batch_op:
        batch_op.alter_column("brand_id", nullable=False)
        batch_op.alter_column("category_id", nullable=False)
        batch_op.create_foreign_key("fk_products_brand_id", "brands", ["brand_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_foreign_key("fk_products_category_id", "product_categories", ["category_id"], ["id"], ondelete="RESTRICT")
        batch_op.create_index("ix_products_brand_id", ["brand_id"])
        batch_op.create_index("ix_products_category_id", ["category_id"])
        batch_op.drop_column("category")
    with op.batch_alter_table("product_repurchase_rules") as batch_op:
        batch_op.drop_column("medical_approval_reference")
        batch_op.drop_column("medical_approved_by")
        batch_op.drop_column("medical_approved_at")


def downgrade() -> None:
    op.add_column("product_repurchase_rules", sa.Column("medical_approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("product_repurchase_rules", sa.Column("medical_approved_by", sa.String(length=255), nullable=True))
    op.add_column("product_repurchase_rules", sa.Column("medical_approval_reference", sa.String(length=120), nullable=True))
    op.add_column("products", sa.Column("category", sa.String(length=120), nullable=True))
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE products SET category = product_categories.name FROM product_categories WHERE products.category_id = product_categories.id"))
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_constraint("fk_products_category_id", type_="foreignkey")
        batch_op.drop_constraint("fk_products_brand_id", type_="foreignkey")
        batch_op.drop_index("ix_products_category_id")
        batch_op.drop_index("ix_products_brand_id")
        batch_op.drop_column("category_id")
        batch_op.drop_column("brand_id")
    op.drop_index("ix_product_categories_name", table_name="product_categories")
    op.drop_table("product_categories")
    op.drop_index("ix_brands_name", table_name="brands")
    op.drop_table("brands")
