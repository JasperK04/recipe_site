from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    FieldList,
    FormField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
    URLField,
)
from wtforms import Form as NoCsrfForm
from wtforms.validators import (
    URL,
    DataRequired,
    EqualTo,
    Length,
    Optional,
    Regexp,
    ValidationError,
)
from wtforms.widgets import CheckboxInput, ListWidget

from app.models import User


class RegistrationForm(FlaskForm):
    """User registration form."""

    username = StringField(
        "Gebruikersnaam",
        validators=[
            DataRequired(),
            Length(
                min=3, max=80, message="Gebruikersnaam moet tussen 3 en 80 tekens zijn."
            ),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message="Gebruikersnaam mag alleen letters, cijfers, punt, streep of underscore bevatten.",
            ),
        ],
    )
    email = StringField(
        "E-mail",
        validators=[
            DataRequired(),
            Regexp(
                r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
                message="Voer een geldig e-mailadres in.",
            ),
        ],
    )
    password = PasswordField(
        "Wachtwoord",
        validators=[
            DataRequired(),
            Length(min=6, message="Wachtwoord moet minimaal 6 tekens lang zijn."),
        ],
    )
    confirm_password = PasswordField(
        "Bevestig wachtwoord",
        validators=[
            DataRequired(),
            EqualTo("password", message="Wachtwoorden moeten overeenkomen."),
        ],
    )
    kitchen_machines = SelectMultipleField(
        "Keukenapparatuur",
        coerce=int,
        validators=[Optional()],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    submit = SubmitField("Registreren")

    def validate_username(self, username):
        """Check if username already exists."""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError("Gebruikersnaam al in gebruik. Kies een andere.")

    def validate_email(self, email):
        """Check if email already exists."""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError(
                "E-mail al geregistreerd. Gebruik een ander e-mailadres."
            )


class LoginForm(FlaskForm):
    """User login form."""

    username = StringField("Gebruikersnaam", validators=[DataRequired()])
    password = PasswordField("Wachtwoord", validators=[DataRequired()])
    submit = SubmitField("Inloggen")


class ProfileForm(FlaskForm):
    """User profile form for updating kitchen machines."""

    kitchen_machines = SelectMultipleField(
        "Keukenapparatuur",
        coerce=int,
        validators=[Optional()],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    submit = SubmitField("Opslaan")


class ProfileEditForm(FlaskForm):
    """Edit profile form with optional password change."""

    username = StringField(
        "Gebruikersnaam",
        validators=[
            DataRequired(),
            Length(
                min=3, max=80, message="Gebruikersnaam moet tussen 3 en 80 tekens zijn."
            ),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message="Gebruikersnaam mag alleen letters, cijfers, punt, streep of underscore bevatten.",
            ),
        ],
    )
    email = StringField(
        "E-mail",
        validators=[
            DataRequired(),
            Regexp(
                r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
                message="Voer een geldig e-mailadres in.",
            ),
        ],
    )
    kitchen_machines = SelectMultipleField(
        "Keukenapparatuur",
        coerce=int,
        validators=[Optional()],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )

    current_password = PasswordField(
        "Huidig wachtwoord",
        validators=[Optional()],
    )
    new_password = PasswordField(
        "Nieuw wachtwoord",
        validators=[
            Optional(),
            Length(min=6, message="Wachtwoord moet minimaal 6 tekens lang zijn."),
        ],
    )
    confirm_new_password = PasswordField(
        "Bevestig nieuw wachtwoord",
        validators=[
            Optional(),
            EqualTo("new_password", message="Wachtwoorden moeten overeenkomen."),
        ],
    )

    submit = SubmitField("Opslaan")

    def validate_username(self, username):
        existing = User.query.filter_by(username=username.data).first()
        if existing and existing.id != current_user.id:
            raise ValidationError("Gebruikersnaam al in gebruik. Kies een andere.")

    def validate_email(self, email):
        existing = User.query.filter_by(email=email.data).first()
        if existing and existing.id != current_user.id:
            raise ValidationError(
                "E-mail al geregistreerd. Gebruik een ander e-mailadres."
            )

    def validate(self, extra_validators=None):  # type: ignore[override]
        if not super().validate(extra_validators=extra_validators):
            return False

        # Password change logic: only enforce when new_password provided
        if self.new_password.data:
            if not self.current_password.data:
                self.current_password.errors = list(self.current_password.errors) + [
                    "Vul je huidige wachtwoord in om het wachtwoord te wijzigen."
                ]
                return False
            if not current_user.check_password(self.current_password.data):
                self.current_password.errors = list(self.current_password.errors) + [
                    "Huidig wachtwoord is onjuist."
                ]
                return False
        return True


class RecipeForm(FlaskForm):
    """Form for adding/editing recipes."""

    title = StringField(
        "Titel",
        validators=[
            DataRequired(),
            Length(max=200, message="Titel moet minder dan 200 tekens bevatten."),
        ],
    )
    description = TextAreaField(
        "Beschrijving",
        validators=[
            Length(max=500, message="Beschrijving moet minder dan 500 tekens zijn.")
        ],
    )

    # Ingredients: a dynamic list of subforms (name, quantity, measurement)
    class IngredientForm(NoCsrfForm):
        name_ = StringField("Naam", validators=[Optional()])
        quantity = StringField("Hoeveelheid", validators=[Optional()])
        measurement = SelectField(
            "Eenheid",
            choices=[
                ("g", "g"),
                ("kg", "kg"),
                ("ml", "ml"),
                ("l", "l"),
                ("el", "el"),
                ("tl", "tl"),
                ("stuks", "stuks"),
            ],
            validators=[Optional()],
        )

    ingredients = FieldList(FormField(IngredientForm), min_entries=1)

    # Instructions: a dynamic list of single-line steps
    instructions = FieldList(
        StringField("Stap", validators=[Optional()]), min_entries=1
    )
    prep_time = StringField(
        "voorbereiding (minuten)",
        validators=[
            Optional(),
            Regexp(r"^\d*$", message="Alleen cijfers"),
        ],
    )
    cook_time = StringField(
        "bereiding (minuten)",
        validators=[
            DataRequired(message="Bereidingstijd is verplicht."),
            Regexp(r"^\d+$", message="Alleen cijfers"),
        ],
    )
    oven_time = StringField(
        "oven (minuten)",
        validators=[
            Optional(),
            Regexp(r"^\d*$", message="Alleen cijfers"),
        ],
    )
    servings = IntegerField("Porties", validators=[Optional()])
    category = SelectField(
        "Categorie",
        choices=[
            ("", "Selecteer een categorie"),
            ("Voorgerecht", "Voorgerecht"),
            ("Ontbijt", "Ontbijt"),
            ("Lunch", "Lunch"),
            ("Diner", "Diner"),
            ("Nagerecht", "Nagerecht"),
            ("Snack", "Snack"),
            ("Drank", "Drank"),
            ("Overig", "Overig"),
        ],
    )
    required_machines = SelectMultipleField(
        "Benodigde keukenapparatuur",
        coerce=int,
        validators=[Optional()],
        widget=ListWidget(prefix_label=False),
        option_widget=CheckboxInput(),
    )
    submit = SubmitField("Opslaan")

    def validate(self, extra_validators=None):  # type: ignore[override]
        is_valid = super().validate(extra_validators=extra_validators)

        # Ingredient validation: if name is provided, quantity and measurement are required
        # If name is empty, ignore the row (even if qty/meas filled) so loose values are discarded
        for entry in self.ingredients:
            name = (entry.name_.data or "").strip()
            qty = (entry.quantity.data or "").strip()
            meas = (entry.measurement.data or "").strip()

            if not name:
                continue

            if not qty:
                entry.quantity.errors = list(entry.quantity.errors) + [
                    "Hoeveelheid is vereist."
                ]
                is_valid = False
            if not meas:
                entry.measurement.errors = list(entry.measurement.errors) + [
                    "Kies een eenheid (of 'Geen eenheid')."
                ]
                is_valid = False

        return is_valid


class ImportRecipeForm(FlaskForm):
    """Form for importing recipe from external URL or document file."""

    url = URLField(
        "Recept URL",
        validators=[
            Optional(),
            URL(message="Voer een geldige URL in"),
        ],
    )

    document = FileField(
        "Of upload een document",
        validators=[
            Optional(),
            FileAllowed(
                ["pdf", "docx", "doc", "txt"],
                "Alleen PDF, DOCX, DOC en TXT bestanden zijn toegestaan.",
            ),
        ],
    )

    submit = SubmitField("Importeren")

    def validate(self, extra_validators=None):  # type: ignore[override]
        if not super().validate(extra_validators=extra_validators):
            return False

        # At least one of url or document must be provided
        if not self.url.data and not self.document.data:
            self.url.errors = list(self.url.errors) + [
                "Vul een URL in of upload een document."
            ]
            return False

        # Only one of url or document should be provided
        if self.url.data and self.document.data:
            self.url.errors = list(self.url.errors) + [
                "Kies ofwel een URL ofwel een document, niet beide."
            ]
            return False

        return True


class AnnotationImportForm(FlaskForm):
    """Form for importing recipe text for annotation from URL or document file."""

    url = URLField(
        "Recept URL",
        validators=[
            Optional(),
            URL(message="Voer een geldige URL in"),
        ],
    )

    document = FileField(
        "Of upload een document",
        validators=[
            Optional(),
            FileAllowed(
                ["pdf", "docx", "doc", "txt"],
                "Alleen PDF, DOCX, DOC en TXT bestanden zijn toegestaan.",
            ),
        ],
    )

    submit = SubmitField("Tekst laden")

    def validate(self, extra_validators=None):  # type: ignore[override]
        if not super().validate(extra_validators=extra_validators):
            return False

        # At least one of url or document must be provided
        if not self.url.data and not self.document.data:
            self.url.errors = list(self.url.errors) + [
                "Vul een URL in of upload een document."
            ]
            return False

        # Only one of url or document should be provided
        if self.url.data and self.document.data:
            self.url.errors = list(self.url.errors) + [
                "Kies ofwel een URL ofwel een document, niet beide."
            ]
            return False

        return True
