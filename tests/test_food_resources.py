import unittest
from datetime import datetime

from app import create_app
from app.extensions import db
from app.models import AlimentoRefrigerado, LecturaTemperatura


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
                "alimento_especifico": "Manzana",
                "temperatura": 30,
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
        self.assertIn(
            "2026-09-24T15:30:45",
            [food["fecha_creacion"] for food in verduras.json],
        )

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

    def test_accepts_testeo_range_boundaries_and_rejects_outside_temperature(self):
        for temperature in (28, 33):
            response = self.client.post(
                "/api/verduras",
                json={"alimento_especifico": "Manzana", "temperatura": temperature},
            )
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json["rango"], "28°C a 33°C")

        response = self.client.post(
            "/api/verduras",
            json={"alimento_especifico": "Manzana", "temperatura": 27.9},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["rango_permitido"], "28°C a 33°C")

    def test_receives_and_persists_arduino_telemetry(self):
        response = self.client.post(
            "/api/lecturas",
            json={
                "producto": "FrutasVerduras",
                "temperatura": 30.4,
                "estado": "OPTIMO",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["producto"], "FrutasVerduras")
        self.assertEqual(response.json["temperatura"], 30.4)
        self.assertEqual(response.json["estado"], "OPTIMO")
        self.assertTrue(response.json["fecha_creacion"].endswith("+00:00"))

        saved_reading = db.session.get(LecturaTemperatura, response.json["id"])
        self.assertEqual(saved_reading.producto, "FrutasVerduras")
        self.assertEqual(saved_reading.estado, "OPTIMO")

        latest = self.client.get("/api/lecturas?limit=1")
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json[0]["id"], response.json["id"])

    def test_accepts_testeo_telemetry_alias(self):
        response = self.client.post(
            "/api/lecturas",
            json={"producto": "Testeo", "temperatura": 28, "estado": "OPTIMO"},
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["producto"], "Testeo")

    def test_receives_new_arduino_profiles_and_persists_all_fields(self):
        readings = (
            {
                "producto": "Frutas_Verduras",
                "temperatura": 10.5,
                "estado": "OPTIMO",
                "tempMin": 8,
                "tempMax": 12,
                "perfil": "2",
            },
            {
                "producto": "Prueba",
                "temperatura": 30,
                "estado": "OPTIMO",
                "tempMin": 29,
                "tempMax": 31,
                "perfil": "3",
            },
        )

        for payload in readings:
            with self.subTest(producto=payload["producto"]):
                response = self.client.post("/api/lecturas", json=payload)

                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json["producto"], payload["producto"])
                self.assertEqual(response.json["tempMin"], payload["tempMin"])
                self.assertEqual(response.json["tempMax"], payload["tempMax"])
                self.assertEqual(response.json["perfil"], payload["perfil"])

                saved_reading = db.session.get(
                    LecturaTemperatura, response.json["id"]
                )
                self.assertEqual(saved_reading.temp_min, payload["tempMin"])
                self.assertEqual(saved_reading.temp_max, payload["tempMax"])
                self.assertEqual(saved_reading.perfil, payload["perfil"])

    def test_rejects_profile_bounds_that_do_not_match_product(self):
        response = self.client.post(
            "/api/lecturas",
            json={
                "producto": "Prueba",
                "temperatura": 30,
                "estado": "OPTIMO",
                "tempMin": 28,
                "tempMax": 33,
                "perfil": "3",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("no coinciden", response.json["error"])

    def test_rejects_telemetry_with_inconsistent_state(self):
        response = self.client.post(
            "/api/lecturas",
            json={
                "producto": "Refrigerados",
                "temperatura": 8,
                "estado": "OPTIMO",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json["estado_esperado"], "ALERTA")

    def test_rejects_disconnected_sensor_reading(self):
        response = self.client.post(
            "/api/lecturas",
            json={
                "producto": "Refrigerados",
                "temperatura": -127,
                "estado": "ALERTA",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("DS18B20", response.json["error"])


if __name__ == "__main__":
    unittest.main()
