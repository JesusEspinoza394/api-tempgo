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

    return app
