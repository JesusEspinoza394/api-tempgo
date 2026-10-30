import hashlib
import hmac
import smtplib
import ssl
from email.message import EmailMessage
from math import ceil
from urllib.parse import urlencode

from flask import Blueprint, current_app, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from ..extensions import db
from ..models import Usuario

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def create_auth_token(user_id):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.dumps({"user_id": user_id})


def decode_auth_token(token):
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return serializer.loads(token, max_age=current_app.config["AUTH_TOKEN_MAX_AGE"])


def create_password_reset_token(user):
    password_fingerprint = hmac.new(
        current_app.config["SECRET_KEY"].encode(),
        user.password_hash.encode(),
        hashlib.sha256,
    ).hexdigest()
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="password-reset"
    )
    return serializer.dumps(
        {"user_id": user.id, "password_fingerprint": password_fingerprint}
    )


def decode_password_reset_token(token):
    serializer = URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="password-reset"
    )
    return serializer.loads(
        token, max_age=current_app.config["PASSWORD_RESET_TOKEN_MAX_AGE"]
    )


def ensure_password_reset_configured(config):
    if config["SECRET_KEY"] == "dev-only-change-this-secret":
        raise RuntimeError("Debe configurarse una clave secreta segura.")

    required_settings = (
        "FRONTEND_URL",
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
    )
    if any(not config.get(setting) for setting in required_settings):
        raise RuntimeError("Falta configurar el servidor SMTP o la URL del frontend.")
    if config["SMTP_USE_TLS"] and config["SMTP_USE_SSL"]:
        raise RuntimeError("SMTP_USE_TLS y SMTP_USE_SSL no pueden usarse a la vez.")


def send_password_reset_email(user, token):
    config = current_app.config
    ensure_password_reset_configured(config)

    reset_url = (
        f'{config["FRONTEND_URL"]}/recuperacion-constraseña?'
        f'{urlencode({"token": token})}'
    )
    message = EmailMessage()
    message["Subject"] = "Recupera tu contraseña de TempGo"
    message["From"] = config["SMTP_FROM"]
    message["To"] = user.email
    expires_in_minutes = max(
        1, ceil(config["PASSWORD_RESET_TOKEN_MAX_AGE"] / 60)
    )
    message.set_content(
        f"Hola {user.nombre},\n\n"
        "Recibimos una solicitud para cambiar la contraseña de tu cuenta TempGo. "
        "Usa este enlace para elegir una nueva contraseña:\n\n"
        f"{reset_url}\n\n"
        f"El enlace vence en {expires_in_minutes} minutos. "
        "Si no solicitaste este cambio, "
        "puedes ignorar este correo.\n"
    )

    context = ssl.create_default_context()
    if config["SMTP_USE_SSL"]:
        with smtplib.SMTP_SSL(
            config["SMTP_HOST"], config["SMTP_PORT"], context=context, timeout=10
        ) as server:
            server.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
            server.send_message(message)
        return

    with smtplib.SMTP(config["SMTP_HOST"], config["SMTP_PORT"], timeout=10) as server:
        if config["SMTP_USE_TLS"]:
            server.starttls(context=context)
        server.login(config["SMTP_USERNAME"], config["SMTP_PASSWORD"])
        server.send_message(message)


def user_to_dict(user):
    return {
        "id": user.id,
        "nombre": user.nombre,
        "email": user.email,
        "edad": user.edad,
        "fecha_creacion": user.fecha_creacion.isoformat(),
    }


@auth_bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    required_fields = ("nombre", "email", "password")
    missing_fields = [field for field in required_fields if not data.get(field)]
    if missing_fields:
        return jsonify({"error": "Faltan campos requeridos", "campos": missing_fields}), 400

    password = data["password"]
    if len(password) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    user = Usuario(
        nombre=data["nombre"],
        email=data["email"].strip().lower(),
        edad=data.get("edad"),
        password_hash=generate_password_hash(password),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "El email ya está registrado"}), 409

    return jsonify({"usuario": user_to_dict(user), "token": create_auth_token(user.id)}), 201


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "El email y la contraseña son requeridos"}), 400

    user = db.session.scalar(db.select(Usuario).where(Usuario.email == email))
    if user is None or not user.password_hash or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Credenciales inválidas"}), 401

    return jsonify({"usuario": user_to_dict(user), "token": create_auth_token(user.id)})


@auth_bp.post("/forgot-password")
def forgot_password():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "")
    if not isinstance(email, str) or not email.strip() or "@" not in email:
        return jsonify({"error": "Ingresa un correo electrónico válido"}), 400
    email = email.strip().lower()

    try:
        ensure_password_reset_configured(current_app.config)
    except RuntimeError as error:
        current_app.logger.error("No se puede procesar la recuperación: %s", error)
        return jsonify({"error": "El servicio de recuperación no está configurado."}), 503

    user = db.session.scalar(db.select(Usuario).where(Usuario.email == email))
    if user is not None and user.password_hash:
        token = create_password_reset_token(user)
        try:
            send_password_reset_email(user, token)
        except (OSError, RuntimeError, ValueError, smtplib.SMTPException):
            current_app.logger.exception("No se pudo enviar el correo de recuperación.")
            return jsonify({"error": "No se pudo enviar el correo de recuperación."}), 503

    return jsonify(
        {
            "message": (
                "Si el correo está asociado a una cuenta, recibirás "
                "instrucciones para recuperar tu contraseña."
            )
        }
    )


@auth_bp.post("/reset-password")
def reset_password():
    data = request.get_json(silent=True) or {}
    token = data.get("token", "")
    password = data.get("password", "")
    if not isinstance(token, str) or not token:
        return jsonify({"error": "El token de recuperación es inválido"}), 400
    if not isinstance(password, str) or not password:
        return jsonify({"error": "El token y la nueva contraseña son requeridos"}), 400
    if len(password) < 8:
        return jsonify({"error": "La contraseña debe tener al menos 8 caracteres"}), 400

    try:
        payload = decode_password_reset_token(token)
    except (BadSignature, SignatureExpired):
        return jsonify({"error": "El enlace de recuperación es inválido o venció"}), 400

    user = db.session.get(Usuario, payload.get("user_id"))
    if user is None or not user.password_hash:
        return jsonify({"error": "El enlace de recuperación es inválido o venció"}), 400

    expected_fingerprint = hmac.new(
        current_app.config["SECRET_KEY"].encode(),
        user.password_hash.encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(
        payload.get("password_fingerprint", ""), expected_fingerprint
    ):
        return jsonify({"error": "El enlace de recuperación ya fue utilizado"}), 400

    user.password_hash = generate_password_hash(password)
    db.session.commit()
    return jsonify({"message": "La contraseña se cambió correctamente"})


@auth_bp.get("/verify")
def verify_token():
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return jsonify({"error": "Se requiere un token Bearer"}), 401

    try:
        payload = decode_auth_token(authorization.removeprefix("Bearer ").strip())
    except (BadSignature, SignatureExpired):
        return jsonify({"error": "Token inválido o expirado"}), 401

    user = db.session.get(Usuario, payload["user_id"])
    if user is None:
        return jsonify({"error": "Usuario no encontrado"}), 401

    return jsonify({"usuario": user_to_dict(user)})
