from flask import Flask, render_template
from extensions import db
from flask_dance.contrib.google import make_google_blueprint
from dotenv import load_dotenv
import os

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1" #HTTP ok, change for production

load_dotenv()
def create_app():
    app = Flask(__name__)

    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///flashcards.db'
    app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback_secret")

    db.init_app(app)

    # Register custom Jinja2 filter
    import jinja_filters
    app.jinja_env.filters['lstrip'] = jinja_filters.lstrip_chars
    app.jinja_env.filters['shuffle'] = jinja_filters.shuffle

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
        from models import User, Flashcard, FlashcardSet
        db.create_all()
        print(db.metadata.tables.keys())
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
