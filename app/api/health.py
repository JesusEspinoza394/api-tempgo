from flask import Blueprint, current_app, jsonify
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db

health_bp = Blueprint("health", __name__)

TELEMETRY_COLUMNS = {
    "id",
    "producto",
    "temperatura",
    "estado",
    "temp_min",
    "temp_max",
    "perfil",
    "fecha_creacion",
}


@health_bp.get("/health")
def health_check():
    response = {"status": "ok", "database": "not_configured"}

    if not current_app.config["DATABASE_CONFIGURED"]:
        return jsonify(response)

    try:
        db.session.execute(text("SELECT 1"))
        response["database"] = "connected"
        inspector = inspect(db.engine)
        if not inspector.has_table("lecturas_temperatura"):
            response["status"] = "degraded"
            response["telemetry"] = "table_missing"
            return jsonify(response), 503

        columns = {
            column["name"]
            for column in inspector.get_columns("lecturas_temperatura")
        }
        missing_columns = sorted(TELEMETRY_COLUMNS - columns)
        if missing_columns:
            response["status"] = "degraded"
            response["telemetry"] = "schema_incomplete"
            response["missing_columns"] = missing_columns
            return jsonify(response), 503

        response["telemetry"] = "ready"
        return jsonify(response)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No se pudo verificar el estado de Neon.")
        response["status"] = "degraded"
        response["database"] = "unavailable"
        return jsonify(response), 503
