from app import create_app
from app.extensions import db
from sqlalchemy import text


def test_health_without_database_configuration():
    class UnconfiguredDatabaseConfig:
        SECRET_KEY = "test-secret"
        AUTH_TOKEN_MAX_AGE = 3600
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        JSON_SORT_KEYS = False
        DATABASE_CONFIGURED = False

    app = create_app(UnconfiguredDatabaseConfig)
    client = app.test_client()

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json == {"status": "ok", "database": "not_configured"}


def test_health_reports_missing_telemetry_schema():
    class ConfiguredDatabaseConfig:
        SECRET_KEY = "test-secret"
        AUTH_TOKEN_MAX_AGE = 3600
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        JSON_SORT_KEYS = False
        DATABASE_CONFIGURED = True

    app = create_app(ConfiguredDatabaseConfig)
    with app.app_context():
        db.session.execute(text(
            "CREATE TABLE lecturas_temperatura ("
            "id INTEGER PRIMARY KEY, "
            "producto VARCHAR(50) NOT NULL, "
            "temperatura FLOAT NOT NULL, "
            "estado VARCHAR(10) NOT NULL, "
            "fecha_creacion DATETIME NOT NULL)"
        ))
        db.session.commit()

        response = app.test_client().get("/api/health")

        assert response.status_code == 503
        assert response.json["database"] == "connected"
        assert response.json["telemetry"] == "schema_incomplete"
        assert response.json["missing_columns"] == ["perfil", "temp_max", "temp_min"]


def test_readings_returns_service_unavailable_for_outdated_schema():
    class ConfiguredDatabaseConfig:
        SECRET_KEY = "test-secret"
        AUTH_TOKEN_MAX_AGE = 3600
        SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        JSON_SORT_KEYS = False
        DATABASE_CONFIGURED = True

    app = create_app(ConfiguredDatabaseConfig)
    with app.app_context():
        db.session.execute(text(
            "CREATE TABLE lecturas_temperatura ("
            "id INTEGER PRIMARY KEY, "
            "producto VARCHAR(50) NOT NULL, "
            "temperatura FLOAT NOT NULL, "
            "estado VARCHAR(10) NOT NULL, "
            "fecha_creacion DATETIME NOT NULL)"
        ))
        db.session.commit()

        response = app.test_client().get("/api/lecturas?limit=5")

        assert response.status_code == 503
        assert "migrate-telemetry" in response.json["error"]
