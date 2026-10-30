import unittest
from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import AlimentoRefrigerado


class TestConfig:
    SECRET_KEY = "test-secret"
    AUTH_TOKEN_MAX_AGE = 3600
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    DATABASE_CONFIGURED = False


class FoodResourcesTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(TestConfig)
        cls.app_context = cls.app.app_context()
        cls.app_context.push()
        db.create_all()
        cls.client = cls.app.test_client()

    @classmethod
    def tearDownClass(cls):
        db.session.remove()
        db.drop_all()
        cls.app_context.pop()

    def test_creates_food_in_each_category(self):
        payloads = {
            "congelados": {"alimento_especifico": "Pollo", "temperatura": -20},
            "refrigerados": {
                "alimento_especifico": "Leche",
                "temperatura": 3,
                "fecha_creacion": "2026-09-24T11:15:30",
            },
            "verduras": {
                "alimento_especifico": "Lechuga",
                "temperatura": 10,
                "fecha_creacion": "2026-09-24T15:30:45",
            },
        }

        for resource, payload in payloads.items():
            response = self.client.post(f"/api/{resource}", json=payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json["alimento_especifico"], payload["alimento_especifico"])
            self.assertEqual(response.json["temperatura"], payload["temperatura"])
            self.assertIn("rango", response.json)

        verduras = self.client.get("/api/verduras")
        self.assertEqual(verduras.json[0]["fecha_creacion"], "2026-09-24T15:30:45")

        saved_food = db.session.scalar(
            db.select(AlimentoRefrigerado).where(
                AlimentoRefrigerado.alimento_especifico == "Leche"
            )
        )
        self.assertEqual(
            saved_food.fecha_creacion,
            datetime.fromisoformat("2026-09-24T11:15:30"),
        )

    def test_rejects_date_without_time(self):
        response = self.client.post(
            "/api/congelados",
            json={
                "alimento_especifico": "Pescado",
                "temperatura": -20,
                "fecha_creacion": "2026-09-24",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("fecha y hora", response.json["error"])

    def test_normalizes_timezone_aware_datetime_to_utc(self):
        response = self.client.post(
            "/api/refrigerados",
            json={
                "alimento_especifico": "Yogur",
                "temperatura": 3,
                "fecha_creacion": "2026-09-24T18:30:00+03:00",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["fecha_creacion"], "2026-09-24T15:30:00")

    def test_rejects_temperature_outside_category_range(self):
        response = self.client.post(
            "/api/congelados",
            json={"alimento_especifico": "Pollo", "temperatura": 10},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["rango_permitido"], "-22°C a -18°C")


if __name__ == "__main__":
    unittest.main()
