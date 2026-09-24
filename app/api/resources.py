from datetime import datetime

from flask import Blueprint, jsonify, request
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import (
    AlimentoCongelado,
    AlimentoRefrigerado,
    AlimentoVerdura,
    Usuario,
)

resources_bp = Blueprint("resources", __name__)

FOOD_RESOURCES = {
    "congelados": {
        "model": AlimentoCongelado,
        "min_temperature": -22,
        "max_temperature": -18,
        "default_range": "-22°C a -18°C",
    },
    "refrigerados": {
        "model": AlimentoRefrigerado,
        "min_temperature": 0,
        "max_temperature": 4,
        "default_range": "0°C a 4°C",
    },
    "verduras": {
        "model": AlimentoVerdura,
        "min_temperature": 8,
        "max_temperature": 12,
        "default_range": "8°C a 12°C",
    },
}


def food_to_dict(food):
    return {
        "id": food.id,
        "alimento_especifico": food.alimento_especifico,
        "temperatura": food.temperatura,
        "rango": food.rango,
        "fecha_creacion": food.fecha_creacion.isoformat(),
    }


def user_to_dict(user):
    return {
        "id": user.id,
        "nombre": user.nombre,
        "email": user.email,
        "edad": user.edad,
        "fecha_creacion": user.fecha_creacion.isoformat(),
    }


@resources_bp.get("/<resource>")
def list_food(resource):
    resource_config = FOOD_RESOURCES.get(resource)
    if resource_config is None:
        return jsonify({"error": "Recurso no encontrado"}), 404

    model = resource_config["model"]
    foods = db.session.scalars(db.select(model).order_by(model.id)).all()
    return jsonify([food_to_dict(food) for food in foods])


@resources_bp.post("/<resource>")
def create_food(resource):
    resource_config = FOOD_RESOURCES.get(resource)
    if resource_config is None:
        return jsonify({"error": "Recurso no encontrado"}), 404

    model = resource_config["model"]
    data = request.get_json(silent=True) or {}
    required_fields = ("alimento_especifico", "temperatura")
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": "Faltan campos requeridos", "campos": missing_fields}), 400

    try:
        temperature = float(data["temperatura"])
    except (TypeError, ValueError):
        return jsonify({"error": "La temperatura debe ser numérica"}), 400

    if not resource_config["min_temperature"] <= temperature <= resource_config["max_temperature"]:
        return jsonify({
            "error": "La temperatura no corresponde a esta categoría",
            "rango_permitido": resource_config["default_range"],
        }), 400

    created_at = datetime.utcnow()
    if data.get("fecha_creacion"):
        try:
            created_at = datetime.fromisoformat(data["fecha_creacion"])
        except (TypeError, ValueError):
            try:
                created_at = datetime.strptime(data["fecha_creacion"], "%d/%m/%Y")
            except (TypeError, ValueError):
                return jsonify({"error": "fecha_creacion debe usar ISO o DD/MM/YYYY"}), 400

    food = model(
        alimento_especifico=data["alimento_especifico"],
        temperatura=temperature,
        rango=data.get("rango") or resource_config["default_range"],
        fecha_creacion=created_at,
    )
    db.session.add(food)
    db.session.commit()
    return jsonify(food_to_dict(food)), 201


@resources_bp.get("/usuarios")
def list_users():
    users = db.session.scalars(db.select(Usuario).order_by(Usuario.id)).all()
    return jsonify([user_to_dict(user) for user in users])


@resources_bp.post("/usuarios")
def create_user():
    data = request.get_json(silent=True) or {}
    required_fields = ("nombre", "email")
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": "Faltan campos requeridos", "campos": missing_fields}), 400

    user = Usuario(
        nombre=data["nombre"],
        email=data["email"],
        edad=data.get("edad"),
    )
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "El email ya está registrado"}), 409

    return jsonify(user_to_dict(user)), 201
