import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from app import create_app
from app.extensions import db


class TestConfig:
    SECRET_KEY = "test-secret"
    AUTH_TOKEN_MAX_AGE = 3600
    PASSWORD_RESET_TOKEN_MAX_AGE = 1800
    FRONTEND_URL = "https://tempgo.example.com"
    SMTP_HOST = "smtp.example.com"
    SMTP_PORT = 587
    SMTP_USERNAME = "smtp-user"
    SMTP_PASSWORD = "smtp-password"
    SMTP_FROM = "noreply@tempgo.example.com"
    SMTP_USE_TLS = True
    SMTP_USE_SSL = False
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

    def test_password_recovery_sends_link_and_resets_password_once(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "nombre": "Beatriz",
                "email": "beatriz@example.com",
                "password": "ClaveSegura123",
            },
        )
        self.assertEqual(registration.status_code, 201)

        with patch("app.api.auth.smtplib.SMTP") as smtp_factory:
            response = self.client.post(
                "/api/auth/forgot-password",
                json={"email": "BEATRIZ@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        smtp = smtp_factory.return_value.__enter__.return_value
        message = smtp.send_message.call_args.args[0]
        self.assertEqual(message["To"], "beatriz@example.com")
        reset_url = next(
            line for line in message.get_content().splitlines()
            if "/recuperacion-constraseña?" in line
        )
        query = parse_qs(urlparse(reset_url).query)
        token = query["token"][0]

        reset = self.client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "NuevaClave123"},
        )
        self.assertEqual(reset.status_code, 200)
        login = self.client.post(
            "/api/auth/login",
            json={"email": "beatriz@example.com", "password": "NuevaClave123"},
        )
        self.assertEqual(login.status_code, 200)

        reused_token = self.client.post(
            "/api/auth/reset-password",
            json={"token": token, "password": "OtraClave123"},
        )
        self.assertEqual(reused_token.status_code, 400)

    def test_password_recovery_does_not_disclose_unknown_emails(self):
        with patch("app.api.auth.smtplib.SMTP") as smtp_factory:
            response = self.client.post(
                "/api/auth/forgot-password",
                json={"email": "desconocido@example.com"},
            )

        self.assertEqual(response.status_code, 200)
        smtp_factory.assert_not_called()

    def test_password_recovery_fails_when_mail_is_unavailable(self):
        registration = self.client.post(
            "/api/auth/register",
            json={
                "nombre": "Carlos",
                "email": "carlos@example.com",
                "password": "ClaveSegura123",
            },
        )
        self.assertEqual(registration.status_code, 201)

        with patch(
            "app.api.auth.smtplib.SMTP", side_effect=OSError("SMTP unavailable")
        ):
            response = self.client.post(
                "/api/auth/forgot-password",
                json={"email": "carlos@example.com"},
            )

        self.assertEqual(response.status_code, 503)


if __name__ == "__main__":
    unittest.main()
