from flask_login import current_user
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    FieldList,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import (
    DataRequired,
    EqualTo,
    Length,
    NumberRange,
    Optional,
    Regexp,
    ValidationError,
)

from app.models import User
from utils.moderation import moderate_username


class RegistrationForm(FlaskForm):
    """User registration form."""

    otc = StringField(
        "One Time Code",
        validators=[
            Optional(),
            Length(min=8, max=8, message="One Time Code moet exact 8 tekens zijn."),
            Regexp(
                r"^[a-z0-9]+$",
                message="One Time Code mag alleen cijfers en letters bevatten.",
            ),
        ],
    )

    username = StringField(
        "Gebruikersnaam *",
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
        "E-mail *",
        validators=[
            DataRequired(),
            Regexp(
                r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
                message="Voer een geldig e-mailadres in.",
            ),
        ],
    )
    password = PasswordField(
        "Wachtwoord *",
        validators=[
            DataRequired(),
            Length(min=6, message="Wachtwoord moet minimaal 6 tekens lang zijn."),
        ],
    )
    confirm_password = PasswordField(
        "Bevestig wachtwoord *",
        validators=[
            DataRequired(),
            EqualTo("password", message="Wachtwoorden moeten overeenkomen."),
        ],
    )
    submit = SubmitField("Registreren")

    def validate_username(self, username):
        """Check if username already exists."""
        moderation = moderate_username(username.data)
        errors = moderation.messages
        user = User.query.filter_by(username=username.data).first()
        if user:
            errors.append("Gebruikersnaam al in gebruik. Kies een andere.")
        if errors:
            raise ValidationError(" ".join(errors))

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


class ProfileEditForm(FlaskForm):
    """Edit profile form with optional password change."""

    username = StringField(
        "Gebruikersnaam *",
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
        "E-mail *",
        validators=[
            DataRequired(),
            Regexp(
                r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$",
                message="Voer een geldig e-mailadres in.",
            ),
        ],
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
            EqualTo("new_password", message="Wachtwoorden moeten overeenkomen."),
        ],
    )

    submit = SubmitField("Opslaan")

    def validate_username(self, username):
        if current_user.is_authenticated and username.data == current_user.username:
            return

        moderation = moderate_username(username.data)
        errors = moderation.messages
        existing = User.query.filter_by(username=username.data).first()
        if existing and existing.id != current_user.id:
            errors.append("Gebruikersnaam al in gebruik. Kies een andere.")
        if errors:
            raise ValidationError(" ".join(errors))

    def validate_email(self, email):
        existing = User.query.filter_by(email=email.data).first()
        if existing and existing.id != current_user.id:
            raise ValidationError(
                "E-mail al geregistreerd. Gebruik een ander e-mailadres."
            )

    def validate_new_password(self, field):
        if field.data and not self.current_password.data:
            raise ValidationError(
                "Vul je huidige wachtwoord in om het wachtwoord te wijzigen."
            )

    def validate_confirm_new_password(self, field):
        if self.new_password.data and not field.data:
            raise ValidationError("Bevestig je nieuwe wachtwoord.")

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


class OTCCreateForm(FlaskForm):
    """Admin form for creating one-time registration codes."""

    purpose = StringField(
        "Voor",
        validators=[
            Optional(),
            Length(
                max=80,
                message="Maximaal 80 tekens lang.",
            ),
        ],
        render_kw={"placeholder": "Bijv. naam of reden voor de code"},
    )
    expires_in_hours = IntegerField(
        "Geldigheid in uren",
        validators=[
            DataRequired(message="Vul een geldige geldigheidsduur in."),
            NumberRange(min=1, message="Kies een duur van minimaal 1 uur."),
        ],
        default=24,
    )
    submit = SubmitField("Aanmaken")


class RecipeForm(FlaskForm):
    """Form for adding/editing recipes."""

    title = StringField(
        "Titel *",
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

    ingredients = FieldList(
        StringField("Ingrediënt", validators=[Optional()]),
        min_entries=1,
        label="Ingrediënten *",
    )

    # Instructions: a dynamic list of single-line steps
    instructions = FieldList(
        StringField("Stap", validators=[Optional()]),
        min_entries=1,
        label="Instructies *",
    )
    prep_time = IntegerField("Bereidingstijd (minuten)", validators=[])
    cook_time = IntegerField("Kooktijd (minuten)", validators=[Optional()])
    servings = IntegerField("Porties", validators=[Optional()])
    category = SelectField(
        "Categorie",
        choices=[
            ("", "Selecteer een categorie"),
            ("Ontbijt", "Ontbijt"),
            ("Lunch", "Lunch"),
            ("Voorgerecht", "Voorgerecht"),
            ("Hoofdgerecht", "Hoofdgerecht"),
            ("Nagerecht", "Nagerecht"),
            ("Snack", "Snack"),
            ("Drank", "Drank"),
            ("Overig", "Overig"),
        ],
    )
    status = SelectField(
        "Status",
        choices=[("public", "Public"), ("draft", "Draft")],
        default="public",
    )
    image = FileField(
        "Afbeelding (jpg/png/webp)",
        validators=[
            Optional(),
            FileAllowed(
                ["jpg", "jpeg", "png", "gif", "webp"], "Only images are allowed"
            ),
        ],
    )
    submit = SubmitField("Opslaan")


class RecipeUploadForm(FlaskForm):
    """Form for uploading recipes."""

    upload_type = SelectField(
        "Type",
        choices=[
            ("url", "URL"),
            ("textarea", "Tekst"),
            ("json", "JSON-bestand"),
            ("text", "Tekstbestand"),
        ],
        validators=[DataRequired()],
        default="url",
    )

    url = StringField(
        "URL van het recept",
        validators=[
            Optional(),
            Regexp(
                r"^(https?://)?(www\.)?[\w-]+(\.[\w-]+)+[/#?]?.*$",
                message="Voer een geldige URL in.",
            ),
        ],
        description="www.example.com/recept",
    )

    textarea = TextAreaField(
        "Tekst van het recept",
        validators=[
            Optional(),
            Length(
                max=5000,
                message="Tekst mag niet langer zijn dan 5.000 tekens.",
            ),
        ],
        render_kw={
            "placeholder": """
Spaghetti Bolognese voor 4 personen
Een klassieke Italiaanse pastasaus met gehakt, tomaat en kruiden.

INGREDIENTEN
400 gram spaghetti
een pond rundergehakt
400 gram gepelde tomaten

STAPPEN
1. Kook de spaghetti volgens de aanwijzingen op de verpakking.
2. Bak het gehakt rul in een grote pan.
3. Voeg de gepelde tomaten toe en laat het geheel 20 minuten sudderen.
""".strip(),
            "style": "min-height: 250px;",
        },
    )

    json_file = FileField(
        "JSON-bestand (export van een recept)",
        validators=[
            Optional(),
            FileAllowed(["json", "jsonl"], "Only JSON files are allowed"),
        ],
    )
    text_file = FileField(
        "Tekstbestand (recept in tekstformaat)",
        validators=[
            Optional(),
            FileAllowed(["txt", "docs", "docx", "pdf"], "Only text files are allowed"),
        ],
    )

    submit = SubmitField("Importeren")

    def validate(self, extra_validators=None):
        if not super().validate(extra_validators):
            return False

        has_url = bool(self.url.data and self.url.data.strip())
        has_textarea = bool(self.textarea.data and self.textarea.data.strip())
        has_json_file = bool(self.json_file.data)
        has_text_file = bool(self.text_file.data)

        type_ = self.upload_type.data
        match type_:
            case "url":
                if not has_url:
                    self.url.errors.append("Vul een URL in.")  # type: ignore
                    return False
            case "textarea":
                if not has_textarea:
                    self.textarea.errors.append("Vul de tekst van het recept in.")  # type: ignore
                    return False
            case "json":
                if not has_json_file:
                    self.json_file.errors.append("Upload een JSON-bestand.")  # type: ignore
                    return False
            case "text":
                if not has_text_file:
                    self.text_file.errors.append("Upload een tekstbestand.")  # type: ignore
                    return False
            case _:
                self.upload_type.errors.append("Ongeldig uploadtype.")  # type: ignore
                return False

        return True
