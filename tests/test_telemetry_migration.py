from sqlalchemy import inspect, text

from app import create_app
from app.extensions import db


class MigrationTestConfig:
    SECRET_KEY = "test-secret"
    AUTH_TOKEN_MAX_AGE = 3600
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    DATABASE_CONFIGURED = False


def test_migrate_telemetry_adds_columns_without_deleting_existing_rows():
    app = create_app(MigrationTestConfig)
    with app.app_context():
        db.session.execute(text(
            "CREATE TABLE lecturas_temperatura ("
            "id INTEGER PRIMARY KEY, "
            "producto VARCHAR(50) NOT NULL, "
            "temperatura FLOAT NOT NULL, "
            "estado VARCHAR(10) NOT NULL, "
            "fecha_creacion DATETIME NOT NULL)"
        ))
        db.session.execute(text(
            "INSERT INTO lecturas_temperatura "
            "(id, producto, temperatura, estado, fecha_creacion) "
            "VALUES (1, 'Refrigerados', 3.2, 'OPTIMO', '2026-11-02 12:00:00')"
        ))
        db.session.commit()

        result = app.test_cli_runner().invoke(args=["migrate-telemetry"])

        assert result.exit_code == 0, result.output
        columns = {
            column["name"]
            for column in inspect(db.engine).get_columns("lecturas_temperatura")
        }
        assert {"temp_min", "temp_max", "perfil"} <= columns
        row = db.session.execute(text(
            "SELECT id, producto, temperatura, estado "
            "FROM lecturas_temperatura WHERE id = 1"
        )).one()
        assert tuple(row) == (1, "Refrigerados", 3.2, "OPTIMO")
