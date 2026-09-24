import unittest

from app import create_app
from app.extensions import db


class TestConfig:
    SECRET_KEY = "test-secret"
    AUTH_TOKEN_MAX_AGE = 3600
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False
    DATABASE_CONFIGURED = False


class AuthTestCase(unittest.TestCase):
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

    def test_register_login_and_verify(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "nombre": "Ana",
                "email": "ana@example.com",
                "password": "ClaveSegura123",
            },
        )
        self.assertEqual(registration.status_code, 201)
        token = registration.json["token"]
        self.assertNotIn("password_hash", registration.json["usuario"])

        login = self.client.post(
            "/api/auth/login",
            json={"email": "ana@example.com", "password": "ClaveSegura123"},
        )
        self.assertEqual(login.status_code, 200)

        invalid_login = self.client.post(
            "/api/auth/login",
            json={"email": "ana@example.com", "password": "incorrecta"},
        )
        self.assertEqual(invalid_login.status_code, 401)

        verification = self.client.get(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(verification.status_code, 200)

    def test_password_must_have_eight_characters(self):
        response = self.client.post(
            "/api/auth/register",
            json={
                "nombre": "Luis",
                "email": "luis@example.com",
                "password": "1234567",
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
