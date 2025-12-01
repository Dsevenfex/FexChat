from flask import Flask
from ext import db
from flask_login import LoginManager
from models import User
from werkzeug.security import generate_password_hash
import main_routes
from dotenv import load_dotenv
import os


load_dotenv()


app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")  #key
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()

    if User.query.count() == 0:
        # Create an admin user
        admin_user = User(
            username="Admin",
            password=generate_password_hash("adminadmin321321"), # your admin password
            role="Admin"  # Set the role to Admin
        )
        db.session.add(admin_user)
        db.session.commit()
        print("Admin user created!")

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Register routes from main_routes
main_routes.register_routes(app)

if __name__ == "__main__":
    app.run(host=os.getenv("HOST"), port=os.getenv("PORT"), debug=os.getenv("FLASK_DEBUG"))
