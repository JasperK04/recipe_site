from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from app.models import User


class RegistrationForm(FlaskForm):
    """User registration form."""
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=80, message='Username must be between 3 and 80 characters.')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Please enter a valid email address.')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=6, message='Password must be at least 6 characters long.')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match.')
    ])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        """Check if username already exists."""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already taken. Please choose a different one.')
    
    def validate_email(self, email):
        """Check if email already exists."""
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered. Please use a different one.')


class LoginForm(FlaskForm):
    """User login form."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')


class RecipeForm(FlaskForm):
    """Form for adding/editing recipes."""
    title = StringField('Recipe Title', validators=[
        DataRequired(),
        Length(max=200, message='Title must be less than 200 characters.')
    ])
    description = TextAreaField('Description', validators=[
        Length(max=500, message='Description must be less than 500 characters.')
    ])
    ingredients = TextAreaField('Ingredients', validators=[
        DataRequired(message='Please list the ingredients.')
    ], description='List ingredients, one per line')
    instructions = TextAreaField('Instructions', validators=[
        DataRequired(message='Please provide cooking instructions.')
    ], description='Step-by-step instructions')
    prep_time = IntegerField('Prep Time (minutes)', validators=[Optional()])
    cook_time = IntegerField('Cook Time (minutes)', validators=[Optional()])
    servings = IntegerField('Servings', validators=[Optional()])
    category = SelectField('Category', choices=[
        ('', 'Select a category'),
        ('appetizer', 'Appetizer'),
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('dessert', 'Dessert'),
        ('snack', 'Snack'),
        ('beverage', 'Beverage'),
        ('other', 'Other')
    ])
    submit = SubmitField('Save Recipe')
