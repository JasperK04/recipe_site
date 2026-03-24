import json
import os
import random
import re
import tempfile

import requests
from bs4 import BeautifulSoup
from faker import Faker
from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import or_
from werkzeug.utils import secure_filename

from app import db
from app.forms import AnnotationImportForm, ImportRecipeForm, RecipeForm
from app.models import KitchenMachine, Recipe
from app.parse_docs import (
    extract_text_from_file,
    parse_document,
    parse_document_with_debug,
)
from app.parsing_model.annotation_scraper import fetch_html as fetch_annotation_html
from app.parsing_model.annotation_scraper import flatten_and_extract_jsonld
from app.parsing_model.torch_model import LABEL_TO_ID, LABELS, preprocess_text
from app.scrapers import fetch_html, scrape_ah_recipe

fake = Faker("nl_NL")


def _normalize_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip().lower()


def _generate_faker_lines(count: int) -> list[list[str]]:
    """Generate `count` lines of faker text, each as a token list."""
    lines = []
    for _ in range(count):
        # Generate a random sentence from faker
        text = fake.sentence()
        # Split into tokens (simple split by whitespace)
        tokens = text.split()
        lines.append(tokens)
    return lines


def _load_annotation_titles() -> set[str]:
    annotations_dir = os.path.join(os.getcwd(), "instance", "annotations")
    titles: set[str] = set()
    if not os.path.exists(annotations_dir):
        return titles

    file_path = os.path.join(annotations_dir, "annotations.json")
    if not os.path.exists(file_path):
        return titles

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return titles

    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                for title in entry.keys():
                    titles.add(_normalize_title(str(title)))

    return titles


def _extract_ah_entries(html: str) -> list[dict[str, object]]:
    soup = BeautifulSoup(html, "html.parser")
    entries: list[dict[str, object]] = []
    seen = set()

    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        if link.get("title"):
            title = str(link.get("title") or "").strip()
        else:
            title = href.split("/")[-1].replace("-", " ").strip()
        if not title or title in seen:
            continue
        if href.startswith("/allerhande/recept/R"):
            seen.add(title)
            entries.append({"title": title, "url": f"https://www.ah.nl{href}"})
        elif href.startswith("https://www.lekkerensimpel.com/"):
            seen.add(title)
            entries.append({"title": title, "url": href})

    return entries


def _normalize_quantity(qty_raw: str):
    """Convert strings with fractions like ½ to float."""
    if not qty_raw:
        return ""

    fraction_map = {
        "¼": 0.25,
        "½": 0.5,
        "¾": 0.75,
        "⅓": 1 / 3,
        "⅔": 2 / 3,
        "⅛": 0.125,
    }

    tokens = re.findall(r"(\d+(?:[.,]\d+)?)|([¼½¾⅓⅔⅛])", qty_raw)
    if not tokens:
        return qty_raw

    total = 0.0
    for num, frac in tokens:
        if num:
            total += float(num.replace(",", "."))
        elif frac:
            total += fraction_map.get(frac, 0)

    return total


recipes_bp = Blueprint("recipes", __name__)


@recipes_bp.route("/")
def list_recipes():
    """Display all recipes."""
    page = request.args.get("page", 1, type=int)
    category = request.args.get("category", None)
    search = request.args.get("search", "")
    filter_by_machines = request.args.get(
        "filter_machines", "1" if current_user.is_authenticated else "0"
    )

    query = Recipe.query

    if category:
        query = query.filter_by(category=category)

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            or_(
                Recipe.title.ilike(search_pattern),
                Recipe.description.ilike(search_pattern),
            )
        )

    # Filter by user's available kitchen machines (default on for authenticated users)
    if current_user.is_authenticated and filter_by_machines == "1":
        user_machine_ids = [m.id for m in current_user.kitchen_machines]
        if user_machine_ids:
            # Only show recipes where all required machines are in user's collection
            # or recipes with no required machines
            query = query.filter(
                or_(
                    ~Recipe.required_machines.any(),  # No required machines
                    Recipe.id.in_(  # All required machines are available
                        db.session.query(Recipe.id)
                        .join(Recipe.required_machines)  # type: ignore
                        .group_by(Recipe.id)
                        .having(
                            db.func.count(KitchenMachine.id)
                            == db.func.sum(
                                db.case(
                                    (KitchenMachine.id.in_(user_machine_ids), 1),
                                    else_=0,
                                )
                            )
                        )
                    ),
                )
            )

    recipes = query.order_by(Recipe.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    return render_template(
        "recipes/list.html",
        recipes=recipes,
        category=category,
        search=search,
        filter_by_machines=filter_by_machines,
    )


@recipes_bp.route("/<int:recipe_id>")
def view_recipe(recipe_id):
    """View a single recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)
    return render_template("recipes/view.html", recipe=recipe)


@recipes_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_recipe():
    """Add a new recipe."""
    form = RecipeForm()

    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.required_machines.choices = [(m.id, m.name) for m in machines]

    # Check if importing from document
    from_document = request.args.get("from_document")
    if from_document and request.method == "GET":
        from flask import session

        scraped_data = session.pop("imported_recipe_data", None)

        if scraped_data:
            try:
                # Prefill form fields
                form.title.data = scraped_data.get("title", "")
                form.description.data = scraped_data.get("description", "")
                form.prep_time.data = (
                    str(scraped_data.get("prep_time"))
                    if scraped_data.get("prep_time")
                    else ""
                )
                form.cook_time.data = (
                    str(scraped_data.get("cook_time"))
                    if scraped_data.get("cook_time")
                    else ""
                )
                form.oven_time.data = (
                    str(scraped_data.get("oven_time"))
                    if scraped_data.get("oven_time")
                    else ""
                )
                form.servings.data = scraped_data.get("servings")
                form.category.data = scraped_data.get("category", "")

                # Prefill ingredients
                form.ingredients.entries.clear()
                for ing in scraped_data.get("ingredients", []):
                    form.ingredients.append_entry(ing)
                if len(form.ingredients.entries) == 0:
                    form.ingredients.append_entry()

                # Prefill instructions
                form.instructions.entries.clear()
                for step in scraped_data.get("instructions", []):
                    form.instructions.append_entry(step)
                if len(form.instructions.entries) == 0:
                    form.instructions.append_entry()

                # Prefill required machines if available
                form.required_machines.data = scraped_data.get("required_machines", [])

                flash(
                    "Document geïmporteerd! Controleer en bewerk indien nodig.",
                    "info",
                )
            except Exception as e:
                flash(f"Fout bij het voorinvullen van formulier: {str(e)}", "danger")

    # Check if importing from AH URL
    ah_url = request.args.get("ah_url")
    if ah_url and request.method == "GET":
        try:
            scraped_data = scrape_ah_recipe(ah_url)

            # Prefill form fields
            form.title.data = scraped_data.get("title", "")
            form.description.data = scraped_data.get("description", "")
            form.prep_time.data = (
                str(scraped_data.get("prep_time"))
                if scraped_data.get("prep_time")
                else ""
            )
            form.cook_time.data = (
                str(scraped_data.get("cook_time"))
                if scraped_data.get("cook_time")
                else ""
            )
            form.oven_time.data = (
                str(scraped_data.get("oven_time"))
                if scraped_data.get("oven_time")
                else ""
            )
            form.servings.data = scraped_data.get("servings")
            form.category.data = scraped_data.get("category", "")

            # Prefill ingredients
            form.ingredients.entries.clear()
            for ing in scraped_data.get("ingredients", []):
                form.ingredients.append_entry(ing)
            if len(form.ingredients.entries) == 0:
                form.ingredients.append_entry()

            # Prefill instructions
            form.instructions.entries.clear()
            for step in scraped_data.get("instructions", []):
                form.instructions.append_entry(step)
            if len(form.instructions.entries) == 0:
                form.instructions.append_entry()

            # Prefill required machines
            form.required_machines.data = scraped_data.get("required_machines", [])

            flash(
                "Recept geïmporteerd! Controleer en bewerk indien nodig.",
                "info",
            )
        except requests.exceptions.RequestException:
            flash(
                "Fout bij ophalen van pagina: Controleer de URL en probeer opnieuw.",
                "danger",
            )
        except ValueError as e:
            flash(f"Fout bij importeren: {str(e)}", "danger")
        except Exception as e:
            flash(f"Onverwachte fout: {str(e)}", "danger")

    if form.validate_on_submit():
        # sanitize ingredient entries: keep only non-empty name or any value
        raw_ingredients = form.ingredients.data or []
        ingredients = []
        for ing in raw_ingredients:
            name = (ing.get("name_") or "").strip()
            qty_raw = (ing.get("quantity") or "").strip()
            measurement = (ing.get("measurement") or "").strip()
            if not name:
                # ignore entries without a name, even if qty/meas present
                continue

            quantity = None
            if qty_raw:
                normalized = _normalize_quantity(qty_raw)
                try:
                    quantity = float(normalized)
                except Exception:
                    quantity = normalized

            ingredients.append(
                {"name_": name, "quantity": quantity, "measurement": measurement}
            )

        prep_time_val = (
            int(form.prep_time.data) if form.prep_time.data else None  # type: ignore[arg-type]
        )
        cook_time_val = int(form.cook_time.data)  # type: ignore[arg-type]
        oven_time_val = (
            int(form.oven_time.data) if form.oven_time.data else None  # type: ignore[arg-type]
        )

        recipe = Recipe(
            title=form.title.data,  # type: ignore
            description=form.description.data,  # type: ignore
            ingredients=ingredients,  # type: ignore
            instructions=form.instructions.data,  # type: ignore
            prep_time=prep_time_val,  # type: ignore
            cook_time=cook_time_val,  # type: ignore
            oven_time=oven_time_val,  # type: ignore
            servings=form.servings.data,  # type: ignore
            category=form.category.data if form.category.data else None,  # type: ignore
            user_id=current_user.id,  # type: ignore
        )

        # Add required kitchen machines
        selected_machine_ids = form.required_machines.data
        if selected_machine_ids:
            selected_machines = KitchenMachine.query.filter(
                KitchenMachine.id.in_(selected_machine_ids)
            ).all()
            recipe.required_machines = selected_machines  # type: ignore

        db.session.add(recipe)
        db.session.commit()
        flash("Recept succesvol toegevoegd!", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template("recipes/form.html", form=form, title="Recept toevoegen")


@recipes_bp.route("/annotate", methods=["GET", "POST"])
@login_required
def annotate_recipe():
    """Annotate recipe text lines for the torch parsing model."""
    form = AnnotationImportForm()
    lines = session.get("annotation_lines")
    source_meta = session.get("annotation_source") or {}
    annotated_lines = source_meta.get("annotated", [])

    if request.method == "GET":
        url_param = request.args.get("url")
        title_param = request.args.get("title")
        if url_param:
            try:
                html = fetch_html(url_param)
                text_list, annotated = flatten_and_extract_jsonld(html)

                # Add faker noise: 3-8 lines before, 1-5 lines after
                noise_before = random.randint(3, 8)
                noise_after = random.randint(1, 5)

                faker_before = _generate_faker_lines(noise_before)
                faker_after = _generate_faker_lines(noise_after)

                # Create annotated entries for faker lines with "other" label
                # Format: [{line_text: label}, ...]
                faker_annotated_before = [
                    {" ".join(line): "other"} for line in faker_before
                ]
                faker_annotated_after = [
                    {" ".join(line): "other"} for line in faker_after
                ]

                # Combine lists
                text_list = faker_before + text_list + faker_after
                annotated = faker_annotated_before + annotated + faker_annotated_after

                source_meta = {
                    "type": "url",
                    "url": url_param,
                    "title": title_param,
                    "text": "\n".join([" ".join(line) for line in text_list]),
                    "annotated": annotated,
                }
                session["annotation_lines"] = text_list
                session["annotation_source"] = source_meta
                return redirect(url_for("recipes.annotate_recipe"))
            except requests.exceptions.RequestException:
                flash(
                    "Fout bij ophalen van pagina: Controleer de URL en probeer opnieuw.",
                    "danger",
                )

    if request.method == "POST":
        action = request.form.get("action", "load")

        if action == "save":
            saved_annotations = []
            idx = 0
            validation_errors = []

            while True:
                # If no text field exists for this index, we've processed all rows
                if f"text-{idx}" not in request.form:
                    break

                text = request.form.get(f"text-{idx}", "").strip()
                label = request.form.get(f"label-{idx}", "").strip()

                # Only validate rows that have text
                if text:
                    if not label or label not in LABEL_TO_ID:
                        validation_errors.append(f"Regel {idx + 1}: label is vereist.")
                    else:
                        saved_annotations.append(
                            {
                                "text": text if isinstance(text, str) else text.split(),
                                "label": label,
                                "label_id": LABEL_TO_ID[label],
                            }
                        )

                idx += 1

            if validation_errors:
                for error in validation_errors:
                    flash(error, "danger")
                return redirect(url_for("recipes.annotate_recipe"))

            inferred_title = None
            for item in saved_annotations:
                if isinstance(item, dict) and item.get("label") == "title":
                    text_value = item.get("text")
                    if isinstance(text_value, str):
                        inferred_title = text_value
                    elif isinstance(text_value, list):
                        inferred_title = " ".join(text_value)
                    break

            title_key = source_meta.get("title") or inferred_title or "Onbekende titel"
            entry = {title_key: saved_annotations}

            annotations_dir = os.path.join(os.getcwd(), "instance", "annotations")
            os.makedirs(annotations_dir, exist_ok=True)
            file_path = os.path.join(annotations_dir, "annotations.json")

            existing = []
            if os.path.exists(file_path):
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            existing = data
                except Exception:
                    existing = []

            existing.append(entry)

            with open(file_path, "w", encoding="utf-8") as f:
                # Custom compact formatting for text arrays
                output = json.dumps(existing, ensure_ascii=False, indent=2)
                # Replace multiline text arrays with single-line format
                output = re.sub(
                    r'"text":\s*\[\s*\n\s*((?:"[^"]*"(?:,\s*\n\s*)?)+)\s*\]',
                    lambda m: '"text": [{}]'.format(
                        ", ".join(re.findall(r'"[^"]*"', m.group(1)))
                    ),
                    output,
                )
                f.write(output)

            session.pop("annotation_lines", None)
            session.pop("annotation_source", None)

            flash("Annotaties opgeslagen.", "success")
            return redirect(url_for("recipes.browse_ah_recipes"))

        if action == "load" and form.validate_on_submit():
            text_list = []
            annotated = []
            source_meta = {}

            if form.url.data:
                html = fetch_html(form.url.data)
                text_list, annotated = flatten_and_extract_jsonld(html)
                source_meta = {
                    "type": "url",
                    "url": form.url.data,
                    "text": "\n".join([" ".join(line) for line in text_list]),
                    "annotated": annotated,
                }

            elif form.document.data:
                file = form.document.data
                filename = secure_filename(file.filename)
                temp_dir = tempfile.gettempdir()
                temp_path = os.path.join(temp_dir, filename)

                try:
                    file.save(temp_path)
                    text = extract_text_from_file(temp_path)
                finally:
                    if os.path.exists(temp_path):
                        os.remove(temp_path)

                text_list = preprocess_text([text])

                source_meta = {
                    "type": "document",
                    "filename": filename,
                    "text": text,
                }

            if not text_list:
                flash("Geen tekst gevonden om te annoteren.", "warning")
                return redirect(url_for("recipes.annotate_recipe"))

            session["annotation_lines"] = text_list
            session["annotation_source"] = source_meta

            flash("Tekst geladen. Label de regels en sla op.", "info")
            return redirect(url_for("recipes.annotate_recipe"))

    return render_template(
        "recipes/annotate.html",
        form=form,
        lines=lines,
        annotated_lines=annotated_lines,
        labels=LABELS,
    )


@recipes_bp.route("/ah/browse")
@login_required
def browse_ah_recipes():
    """Browse AH recipes and link to annotation page."""
    page = request.args.get("page", 1, type=int)
    max_pages = request.args.get("max_pages", 5, type=int)
    existing_titles = _load_annotation_titles()

    entries = []
    current_page = page
    page_url = ""

    for _ in range(max_pages):
        page_url = f"https://www.ah.nl/allerhande/recepten-zoeken?page={current_page}"
        # page_url = f"https://www.lekkerensimpel.com/hoofdgerechten/"
        html = fetch_annotation_html(page_url)
        entries = _extract_ah_entries(html)

        for entry in entries:
            normalized = _normalize_title(str(entry["title"]))
            entry["disabled"] = normalized in existing_titles

        if entries and any(not entry["disabled"] for entry in entries):
            break

        current_page += 1

    return render_template(
        "recipes/ah_list.html",
        entries=entries,
        page=current_page,
        source_url=page_url,
    )


@recipes_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_recipe():
    """Import a recipe from an external URL or document file."""
    form = ImportRecipeForm()

    # Disclaimer shown on the import page to set expectations
    if request.method == "GET":
        flash(
            "Let op: De importfunctie is generiek en site-afhankelijk. Controleer altijd de geïmporteerde ingrediënten, tijden en porties.",
            "warning",
        )

    if form.validate_on_submit():
        # Handle URL import
        if form.url.data:
            return redirect(url_for("recipes.add_recipe", ah_url=form.url.data))

        # Handle document import
        if form.document.data:
            file = form.document.data
            filename = secure_filename(file.filename)

            # Create a temporary file to store the upload
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, filename)

            try:
                # Save the uploaded file
                file.save(temp_path)

                # DEBUG MODE: Set PARSE_DEBUG_MODE in .env file to enable/disable
                DEBUG_MODE = (
                    os.environ.get("PARSE_DEBUG_MODE", "False").lower() == "true"
                )

                if DEBUG_MODE:
                    # Debug mode: keep file and redirect to debug page
                    return redirect(url_for("recipes.debug_parse", filename=filename))
                else:
                    # Normal mode: parse and redirect to add_recipe
                    parsed_data = parse_document(temp_path)

                    # Store data in session for complex data structures
                    from flask import session

                    session["imported_recipe_data"] = parsed_data

                    # Clean up the temporary file
                    os.remove(temp_path)

                    return redirect(url_for("recipes.add_recipe", from_document=1))

            except ImportError as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                flash(
                    f"Ontbrekende afhankelijkheid: {str(e)}",
                    "danger",
                )
            except ValueError as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                flash(f"Fout bij het verwerken van document: {str(e)}", "danger")
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                flash(f"Onverwachte fout bij document import: {str(e)}", "danger")

    return render_template("recipes/import.html", form=form)


@recipes_bp.route("/debug-parse/<filename>")
@login_required
def debug_parse(filename):
    """Debug page to view all intermediate parsing steps."""

    # Get the uploaded file path
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, secure_filename(filename))

    if not os.path.exists(temp_path):
        flash("Debug file not found. Please re-upload the document.", "danger")
        return redirect(url_for("recipes.import_recipe"))

    try:
        # Parse with debug info - returns all intermediate steps
        debug_data = parse_document_with_debug(temp_path)

        # Store parsed recipe data in session for potential use
        session["imported_recipe_data"] = debug_data["parsed_recipe"]

        # Clean up the temporary file
        os.remove(temp_path)

        return render_template(
            "recipes/debug_parse.html",
            debug_data=debug_data,
        )

    except Exception as e:
        if os.path.exists(temp_path):
            os.remove(temp_path)
        flash(f"Error during debug parsing: {str(e)}", "danger")
        return redirect(url_for("recipes.import_recipe"))


@recipes_bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit_recipe(recipe_id):
    """Edit an existing recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Only the author can edit their recipe
    if recipe.user_id != current_user.id:
        abort(403)

    # Build a fresh form instance and populate scalar fields and FieldLists
    form = RecipeForm()

    # Populate kitchen machines choices
    machines = KitchenMachine.query.order_by(KitchenMachine.name).all()
    form.required_machines.choices = [(m.id, m.name) for m in machines]

    if request.method == "GET":
        # simple fields
        form.title.data = recipe.title
        form.description.data = recipe.description
        form.prep_time.data = recipe.prep_time
        form.cook_time.data = recipe.cook_time
        form.oven_time.data = recipe.oven_time
        form.servings.data = recipe.servings
        form.category.data = recipe.category if recipe.category else ""

        # Pre-populate required machines
        form.required_machines.data = [m.id for m in recipe.required_machines]

        # populate ingredients FieldList
        try:
            form.ingredients.entries.clear()
        except Exception:
            pass
        for ing in recipe.ingredients or []:
            form.ingredients.append_entry(
                {
                    "name_": ing.get("name_", ""),
                    "quantity": str(ing.get("quantity", "") or ""),
                    "measurement": ing.get("measurement", "") or "",
                }
            )
        if len(form.ingredients.entries) == 0:
            form.ingredients.append_entry()

        # populate instructions FieldList
        try:
            form.instructions.entries.clear()
        except Exception:
            pass
        for step in recipe.instructions or []:
            form.instructions.append_entry(step)
        if len(form.instructions.entries) == 0:
            form.instructions.append_entry()
    if form.validate_on_submit():
        # sanitize as in add_recipe
        raw_ingredients = form.ingredients.data or []
        ingredients = []
        for ing in raw_ingredients:
            name = (ing.get("name_") or "").strip()
            qty_raw = (ing.get("quantity") or "").strip()
            measurement = (ing.get("measurement") or "").strip()
            if not name:
                # ignore entries without a name, even if qty/meas present
                continue
            try:
                normalized = _normalize_quantity(qty_raw)
                quantity = float(normalized) if qty_raw else None
            except Exception:
                quantity = normalized
            ingredients.append(
                {"name_": name, "quantity": quantity, "measurement": measurement}
            )

        raw_steps = form.instructions.data or []
        instructions = [step for step in raw_steps if step.strip()]

        recipe.title = form.title.data
        recipe.description = form.description.data
        recipe.ingredients = ingredients
        recipe.instructions = instructions
        recipe.prep_time = int(form.prep_time.data) if form.prep_time.data else None
        recipe.cook_time = int(form.cook_time.data)
        recipe.oven_time = int(form.oven_time.data) if form.oven_time.data else None
        recipe.servings = form.servings.data
        recipe.category = form.category.data if form.category.data else None

        # Update required kitchen machines
        selected_machine_ids = form.required_machines.data
        if selected_machine_ids:
            selected_machines = KitchenMachine.query.filter(
                KitchenMachine.id.in_(selected_machine_ids)
            ).all()
            recipe.required_machines = selected_machines
        else:
            recipe.required_machines = []

        db.session.commit()
        flash("Recept succesvol bijgewerkt!", "success")
        return redirect(url_for("recipes.view_recipe", recipe_id=recipe.id))

    return render_template(
        "recipes/form.html", form=form, title="Recept bewerken", recipe=recipe
    )


@recipes_bp.route("/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete_recipe(recipe_id):
    """Delete a recipe."""
    recipe = Recipe.query.get_or_404(recipe_id)

    # Only the author can delete their recipe
    if recipe.user_id != current_user.id:
        abort(403)

    db.session.delete(recipe)
    db.session.commit()
    flash("Recept succesvol verwijderd!", "success")
    return redirect(url_for("recipes.list_recipes"))


@recipes_bp.route("/my-recipes")
@login_required
def my_recipes():
    """Display current user's recipes."""
    page = request.args.get("page", 1, type=int)
    recipes = (
        Recipe.query.filter_by(user_id=current_user.id)
        .order_by(Recipe.created_at.desc())
        .paginate(page=page, per_page=12, error_out=False)
    )

    return render_template("recipes/my_recipes.html", recipes=recipes)
