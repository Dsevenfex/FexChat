from flask_sqlalchemy import SQLAlchemy
from ext import db
from datetime import datetime
from flask_login import UserMixin


class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    pfp = db.Column(db.String, nullable=True, default="pfp.png")
    is_system = db.Column(db.Boolean, default=False)  #
    role = db.Column(db.String, default="User")
    last_post_time = db.Column(db.DateTime, default=datetime.utcnow)
    posts = db.relationship("Post", backref="author", lazy=True)
    custom_color_class = db.Column(db.String(50), default='u-blue')
    is_muted = db.Column(db.Boolean, default=False)
    mute_until = db.Column(db.DateTime, nullable=True)


class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    rate_limit_seconds = db.Column(db.Float, default=1.0)  

    


class Post(db.Model):
    __tablename__ = "posts" 

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True) # nullable=True to allow SYSTEM posts
    user_message = db.Column(db.String(255), nullable=False) # Increased limit for message

    # Used for global announcements and system generated messages (/say, /mute)
    is_system = db.Column(db.Boolean, default=False)
    # Used for /me commands (emote messages)
    is_emote = db.Column(db.Boolean, default=False)