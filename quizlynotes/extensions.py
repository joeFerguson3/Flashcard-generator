from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import current_user

db = SQLAlchemy()
migrate = Migrate()
csrf = CSRFProtect()
login_manager = LoginManager()


def rate_limit_key() -> str:
    """Limit signed-in users per account, everyone else per IP."""
    try:
        if current_user.is_authenticated:
            return f"user:{current_user.id}"
    except Exception:  # pragma: no cover - outside request context
        pass
    return get_remote_address()


limiter = Limiter(key_func=rate_limit_key, default_limits=[])
