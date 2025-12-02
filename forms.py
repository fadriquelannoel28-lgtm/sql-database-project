# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, SubmitField, FileField, DateTimeLocalField, FileField, DecimalField
from wtforms.validators import DataRequired, Email, Length, EqualTo, NumberRange
from flask_wtf.file import FileField, FileAllowed

# ----------------------------------------Contact Form 
class ContactForm(FlaskForm):
    name = StringField(
        'Name', 
        validators=[DataRequired(message="Please enter your name"), Length(max=50)]
    )
    email = StringField(
        'Email Address', 
        validators=[DataRequired(message="Please enter your email"), Email(message="Enter a valid email"), Length(max=100)]
    )
    message = TextAreaField(
        'Message', 
        validators=[DataRequired(message="Please write your message"), Length(max=500)]
    )
    submit = SubmitField('Send Message')

# ----------------------------------------Login Form
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')
# ----------------------------------------Registration Form 
class RegisterForm(FlaskForm):
    fullname = StringField(
        'Full Name', 
        validators=[DataRequired(message="Enter your full name"), Length(max=100)]
    )
    username = StringField(
        'Username', 
        validators=[DataRequired(message="Enter your username"), Length(max=50)]
    )
    email = StringField(
        'Email Address', 
        validators=[DataRequired(message="Enter your email"), Email(), Length(max=100)]
    )
    password = PasswordField(
        'Password', 
        validators=[DataRequired(message="Enter your password"), Length(min=6)]
    )
    confirm_password = PasswordField(
        'Confirm Password', 
        validators=[DataRequired(message="Confirm your password"), EqualTo('password', message="Passwords must match")]
    )
    submit = SubmitField('Register')

# ----------------------------------------Event Form (Report) 
class EventForm(FlaskForm):
    event_name = StringField(
        'Event Name', 
        validators=[DataRequired(), Length(max=100)]
    )
    location = StringField(
        'Location', 
        validators=[DataRequired(), Length(max=100)]
    )
    description = TextAreaField(
        'Description', 
        validators=[DataRequired(), Length(max=500)]
    )
    datetime = StringField(
        'Event Date and Time', 
        validators=[DataRequired()]
    )
    participants = IntegerField(
        'Max Participants', 
        validators=[NumberRange(min=1, max=1000)]
    )
    image = FileField('Upload Image')
    submit = SubmitField('Create Event')

# ----------------------------------------Report
class EventForm(FlaskForm):
    event_name = StringField("Event Name", validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired()])
    description = TextAreaField("Description", validators=[DataRequired()])
    datetime = DateTimeLocalField("Date & Time", format="%Y-%m-%dT%H:%M", validators=[DataRequired()])
    participants = IntegerField("Max Participants", default=50, validators=[NumberRange(min=1, max=50)])
    image = FileField("Image")
    submit = SubmitField("Create Event")

# ----------------------------------------Community

class CommunityForm(FlaskForm):
    description = TextAreaField('Description', validators=[DataRequired(), Length(max=500)])
    picture = FileField('Picture', validators=[FileAllowed(['jpg', 'jpeg', 'png'], 'Images only!')])
    submit = SubmitField('Post')