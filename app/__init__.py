from flask import Flask
from flask_cors import CORS
from sqlalchemy import inspect, text

from .config import Config
from .extensions import db
from .api import api_bp
from . import models


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    CORS(app, resources={r"/api/*": {"origins": "*", "send_wildcard": True}})

    db.init_app(app)
    app.register_blueprint(api_bp, url_prefix="/api")

    @app.get("/")
    def index():
        return {"name": "TempGo API", "status": "ok", "health": "/api/health"}

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        print("Tablas creadas correctamente.")

    @app.cli.command("migrate-auth")
    def migrate_auth():
        inspector = inspect(db.engine)
        columns = {column["name"] for column in inspector.get_columns("usuarios")}
        if "password_hash" not in columns:
            with db.engine.begin() as connection:
                connection.execute(text("ALTER TABLE usuarios ADD COLUMN password_hash VARCHAR(255)"))
        print("Columna de autenticación verificada correctamente.")

    @app.cli.command("migrate-telemetry")
    def migrate_telemetry():
        db.create_all()
        inspector = inspect(db.engine)
        columns = {
            column["name"]
            for column in inspector.get_columns("lecturas_temperatura")
        }
        additions = {
            "temp_min": "FLOAT",
            "temp_max": "FLOAT",
            "perfil": "VARCHAR(1)",
        }
        with db.engine.begin() as connection:
            for column, column_type in additions.items():
                if column not in columns:
                    connection.execute(text(
                        f"ALTER TABLE lecturas_temperatura "
                        f"ADD COLUMN {column} {column_type}"
                    ))
        print("Columnas de lecturas de temperatura verificadas correctamente.")

    return app
