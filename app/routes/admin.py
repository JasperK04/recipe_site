from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from flask import (
    Blueprint,
    Response,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_

from app import db
from app.api import (
    ApiError,
    deactivate_recipe,
    deactivate_user,
    demote_user,
    pending_recipe_moderation_count,
    promote_user,
    reactivate_recipe,
    reactivate_user,
)
from app.api.users import (
    create_registration_otc,
    pending_creator_request_count,
)
from app.forms import OTCCreateForm
from app.models import Credential, Recipe, User
from app.navigation import safe_referrer_url
from utils import require_active_admin

admin_bp = Blueprint("admin", __name__)


def _panel_context(*, section: str) -> Any:
    stats = {
        "pending_creator_requests": pending_creator_request_count(),
        "pending_recipe_moderation": pending_recipe_moderation_count(),
        "active_otcs": Credential.query.filter(
            Credential.purpose == "registration_invitation",
            Credential.expires_at > datetime.now(),  # noqa: DTZ005
            Credential.revoked_at.is_(None),
            Credential.used_at.is_(None),
        ).count(),
    }

    context = {
        "section": section,
        "stats": stats,
    }

    if section == "users":
        context["users"] = User.query.order_by(
            db.text("is_active DESC"), User.username.asc()
        ).all()
    elif section == "recipes":
        page = request.args.get("page", 1, type=int)
        status = request.args.get("status", "all")
        moderation = request.args.get("moderation", "all")
        search = request.args.get("search", "")

        query = Recipe.query
        if status in Recipe.VALID_STATUSES:
            query = query.filter_by(status=status)
        if moderation == "flagged":
            query = query.filter(Recipe.moderation_status == "flagged")
        elif moderation == "allowed":
            query = query.filter(Recipe.moderation_status == "allowed")
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Recipe.title.ilike(search_pattern),
                    Recipe.description.ilike(search_pattern),
                )
            )
        context.update(
            {
                "recipes": query.order_by(Recipe.created_at.desc()).paginate(
                    page=page, per_page=24, error_out=False
                ),
                "status": status,
                "moderation": moderation,
                "search": search,
            }
        )
    elif section == "otc":
        form = OTCCreateForm()
        created_otc = session.pop("created_otc", None)
        registration_link = session.pop("registration_link", None)

        if created_otc:
            created_otc["expires_at"] = datetime.fromisoformat(
                created_otc["expires_at"]
            )

        if form.validate_on_submit():
            try:
                expires_in_hours = form.expires_in_hours.data
                if expires_in_hours is None:
                    raise ApiError("Controleer de invoer.", 400)
                created_otc = create_registration_otc(
                    expires_in_hours=expires_in_hours,
                    purpose=form.purpose.data,
                )
            except ApiError as error:
                flash(error.message, "danger")
            else:
                registration_link = url_for(
                    "auth.register", otc=created_otc[1], _external=True
                )
                session["created_otc"] = {
                    "code": created_otc[1],
                    "purpose": form.purpose.data,
                    "expires_at": created_otc[0].expires_at.isoformat(),
                }
                session["registration_link"] = registration_link
                flash("OTC aangemaakt voor een leerling kok-registratie.", "success")
                return redirect(url_for("admin.manage_otc"))

        context.update(
            {
                "form": form,
                "active_otcs": Credential.query.filter(
                    Credential.purpose == "registration_invitation",
                    Credential.expires_at > datetime.now(),  # noqa: DTZ005
                    Credential.revoked_at.is_(None),
                    Credential.used_at.is_(None),
                )
                .order_by(Credential.expires_at.asc(), Credential.created_at.desc())
                .all(),
                "created_otc": created_otc,
                "registration_link": registration_link,
            }
        )

    return cast(dict[str, Any], context)


def _user_row_response(user: User):
    return jsonify(
        {
            "status": "ok",
            "pending_creator_requests": pending_creator_request_count(),
            "html": render_template(
                "components/user_table_row.html",
                user=user,
                current_user=current_user,
            ),
        }
    )


def _json_error(error: ApiError):
    return jsonify({"status": "error", "message": error.message}), error.status_code


@admin_bp.route("/")
@login_required
def panel():
    require_active_admin(current_user)
    return render_template("admin/panel.html", **_panel_context(section="dashboard"))


@admin_bp.route("/users")
@login_required
def users():
    require_active_admin(current_user)
    return render_template("admin/panel.html", **_panel_context(section="users"))


@admin_bp.route("/users/<int:user_id>/deactivate", methods=["POST"])
@login_required
def deactivate_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    try:
        deactivate_user(actor=admin_user, target=target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@admin_bp.route("/users/<int:user_id>/reactivate", methods=["POST"])
@login_required
def reactivate_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    reactivate_user(target)
    return _user_row_response(target)


@admin_bp.route("/users/<int:user_id>/promote", methods=["POST"])
@login_required
def promote_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    try:
        promote_user(target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@admin_bp.route("/users/<int:user_id>/demote", methods=["POST"])
@login_required
def demote_user_route(user_id):
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    target = User.query.get_or_404(user_id)

    try:
        demote_user(target)
    except ApiError as error:
        return _json_error(error)

    return _user_row_response(target)


@admin_bp.route("/recipes")
@login_required
def recipes():
    require_active_admin(current_user)
    return render_template("admin/panel.html", **_panel_context(section="recipes"))


@admin_bp.route("/recipes/<int:recipe_id>/deactivate", methods=["POST"])
@login_required
def deactivate_recipe_route(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    already_deactivated = recipe.status == Recipe.STATUS_DEACTIVATED
    deactivate_recipe(recipe)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            {
                "status": "ok",
                "new_status": recipe.status,
                "pending_recipe_moderation": pending_recipe_moderation_count(),
            }
        )
    if already_deactivated:
        flash("Recept is al gedeactiveerd.", "info")
    else:
        flash("Recept gedeactiveerd.", "success")
    return redirect(safe_referrer_url() or url_for("admin.recipes"))


@admin_bp.route("/recipes/<int:recipe_id>/reactivate", methods=["POST"])
@login_required
def reactivate_recipe_route(recipe_id):
    require_active_admin(current_user)
    recipe = Recipe.query.get_or_404(recipe_id)
    already_active = recipe.status != Recipe.STATUS_DEACTIVATED
    reactivate_recipe(recipe)
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify(
            {
                "status": "ok",
                "new_status": recipe.status,
                "pending_recipe_moderation": pending_recipe_moderation_count(),
            }
        )
    if already_active:
        flash("Recept is al actief.", "info")
    else:
        flash("Recept opnieuw geactiveerd.", "success")
    return redirect(safe_referrer_url() or url_for("admin.recipes"))


@admin_bp.route("/otc", methods=["GET", "POST"])
@login_required
def manage_otc():
    require_active_admin(current_user)
    context = _panel_context(section="otc")
    if isinstance(context, Response):
        return context
    return render_template("admin/panel.html", **context)


@admin_bp.route("/otc/<int:credential_id>/delete", methods=["POST"])
@login_required
def delete_otc(credential_id: int):
    """Delete a registration invitation from the dashboard."""
    admin_user = cast(User, current_user)
    require_active_admin(admin_user)
    credential = Credential.query.filter_by(
        id=credential_id, purpose="registration_invitation"
    ).first_or_404()
    db.session.delete(credential)
    db.session.commit()
    flash("Registratie-uitnodiging verwijderd.", "success")
    return redirect(url_for("admin.manage_otc"))
