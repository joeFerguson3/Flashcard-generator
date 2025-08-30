from flask import Flask
from extensions import db
from flask_dance.contrib.google import make_google_blueprint
import os

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" #HTTP ok, change for production

def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashcards.db'
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret")

    db.init_app(app)

    # Google OAuth
    google_bp = make_google_blueprint(
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scope=["openid",
        "https://www.googleapis.com/auth/userinfo.email",
        "https://www.googleapis.com/auth/userinfo.profile"]
    )
    app.register_blueprint(google_bp, url_prefix="/login")

    # Import blueprints
    from routes.auth import auth_bp
    from routes.flashcards import flashcards_bp
    from routes.main import main_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(flashcards_bp)
    app.register_blueprint(main_bp)

    with app.app_context():
        db.create_all()

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
