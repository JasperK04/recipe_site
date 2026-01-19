from flask_wtf import FlaskForm
from wtforms import (
    FieldList,
    FormField,
    IntegerField,
    PasswordField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms import Form as NoCsrfForm
from wtforms.validators import (
    DataRequired,
    Email,
    EqualTo,
    Length,
    Optional,
    ValidationError,
)

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
        ],
    )
    email = StringField(
        "E-mail",
        validators=[DataRequired(), Email(message="Voer een geldig e-mailadres in.")],
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
    prep_time = IntegerField("Bereidingstijd (minuten)", validators=[])
    cook_time = IntegerField("Kooktijd (minuten)", validators=[Optional()])
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
    submit = SubmitField("Opslaan")
