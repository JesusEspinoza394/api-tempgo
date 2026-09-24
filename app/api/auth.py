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
