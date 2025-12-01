from flask_wtf import FlaskForm
from wtforms import StringField,SubmitField,PasswordField
from wtforms.validators import Length, DataRequired, Regexp, EqualTo


class LoginForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired()])
    password = PasswordField("Password", validators=[DataRequired()])
    login = SubmitField("Login")

class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=4, max=15), Regexp(r'^[A-Za-z0-9_]*$', message="Username must only contain letters, numbers, and underscores.")])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8, max=20)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo('password', message="Passwords must match.")])
    register = SubmitField("Register")
class PostForm(FlaskForm):
    message = StringField("Message", validators=[DataRequired(), Length(min=1 ,max=200)])
    post_submit = SubmitField("Send")
