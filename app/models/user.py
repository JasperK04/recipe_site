from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from flask_login import UserMixin
from sqlalchemy import text
from werkzeug.security import check_password_hash, generate_password_hash

from app import db
from app.models.common import users_favorites


class User(UserMixin, db.Model):
    __tablename__ = "users"

    ROLE_FIJNPROEVER = 1
    ROLE_LEERLING_KOK = 2
    ROLE_ZELFSTANDIG_KOK = 3
    ROLE_CHEF_DE_PARTIE = 4
    ROLE_SOUS_CHEF = 5
    ROLE_CHEF_DE_CUISINE = 6
    VALID_ROLES = (
        ROLE_FIJNPROEVER,
        ROLE_LEERLING_KOK,
        ROLE_ZELFSTANDIG_KOK,
        ROLE_CHEF_DE_PARTIE,
        ROLE_SOUS_CHEF,
        ROLE_CHEF_DE_CUISINE,
    )

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(
        db.Integer,
        nullable=False,
        default=ROLE_FIJNPROEVER,
        server_default=text(str(ROLE_FIJNPROEVER)),
    )
    is_active = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    creator_request_pending = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    recipes = db.relationship(
        "Recipe", backref="author", lazy="dynamic", cascade="all, delete-orphan"
    )
    favorites = db.relationship(
        "Recipe",
        secondary=users_favorites,
        lazy="dynamic",
        backref=db.backref("favorited_by", lazy="dynamic"),
    )
    scores = db.relationship("RecipeScore", back_populates="user", cascade="all, delete-orphan")

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_role_label(self):
        role_labels = {
            self.ROLE_FIJNPROEVER: "Fijnproever",
            self.ROLE_LEERLING_KOK: "Leerling Kok",
            self.ROLE_ZELFSTANDIG_KOK: "Zelfstandig Kok",
            self.ROLE_CHEF_DE_PARTIE: "Chef de Partie",
            self.ROLE_SOUS_CHEF: "Sous Chef",
            self.ROLE_CHEF_DE_CUISINE: "Chef de Cuisine",
        }
        return role_labels.get(self.role, "Onbekend")

    @property
    def is_admin(self):
        return self.role == self.ROLE_CHEF_DE_CUISINE

    @property
    def is_creator(self):
        return self.role >= self.ROLE_LEERLING_KOK

    @property
    def can_create_recipes(self):
        return bool(self.is_active and self.is_creator)

    @property
    def can_score_recipes(self):
        return bool(self.is_active and self.role >= self.ROLE_FIJNPROEVER)

    def __repr__(self):
        return f"<User {self.username}>"
