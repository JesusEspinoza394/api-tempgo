from flask import Blueprint

from .health import health_bp
from .resources import resources_bp
from .auth import auth_bp

api_bp = Blueprint("api", __name__)
api_bp.register_blueprint(health_bp)
api_bp.register_blueprint(resources_bp)
api_bp.register_blueprint(auth_bp)
