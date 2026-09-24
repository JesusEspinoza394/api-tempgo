from flask import Blueprint, current_app, jsonify
from sqlalchemy import text

from ..extensions import db

health_bp = Blueprint("health", __name__)


@health_bp.get("/health")
def health_check():
    response = {"status": "ok", "database": "not_configured"}

    if not current_app.config["DATABASE_CONFIGURED"]:
        return jsonify(response)

    try:
        db.session.execute(text("SELECT 1"))
        response["database"] = "connected"
        return jsonify(response)
    except Exception:
        db.session.rollback()
        response["status"] = "degraded"
        response["database"] = "unavailable"
        return jsonify(response), 503
