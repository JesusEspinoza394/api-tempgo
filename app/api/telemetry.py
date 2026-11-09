from datetime import datetime, timezone
import math

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import SQLAlchemyError

from ..extensions import db
from ..models import LecturaTemperatura

telemetry_bp = Blueprint("telemetry", __name__)

PRODUCT_PROFILES = {
    "Refrigerados": ("1", 0, 4),
    "Frutas_Verduras": ("2", 8, 12),
    "Prueba": ("3", 29, 31),
    "FrutasVerduras": ("2", 28, 33),
    "Testeo": ("3", 29, 31),
    "Congelados": ("3", -22, -16),
}


def reading_to_dict(reading):
    created_at = reading.fecha_creacion
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    return {
        "id": reading.id,
        "producto": reading.producto,
        "temperatura": reading.temperatura,
        "estado": reading.estado,
        "tempMin": reading.temp_min,
        "tempMax": reading.temp_max,
        "perfil": reading.perfil,
        "fecha_creacion": created_at.astimezone(timezone.utc).isoformat(),
    }


@telemetry_bp.route("/lecturas", methods=["GET", "POST"])
def readings():
    if request.method == "GET":
        try:
            limit = int(request.args.get("limit", "100"))
        except ValueError:
            return jsonify({"error": "limit debe ser un número entero"}), 400
        if not 1 <= limit <= 500:
            return jsonify({"error": "limit debe estar entre 1 y 500"}), 400

        try:
            results = db.session.scalars(
                db.select(LecturaTemperatura)
                .order_by(
                    LecturaTemperatura.fecha_creacion.desc(),
                    LecturaTemperatura.id.desc(),
                )
                .limit(limit)
            ).all()
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception(
                "No se pudieron consultar las lecturas de temperatura."
            )
            return jsonify({
                "error": (
                    "No se pudieron consultar las lecturas. "
                    "Verifica el esquema con la migración migrate-telemetry."
                )
            }), 503
        return jsonify([reading_to_dict(item) for item in results])

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON"}), 400

    required_fields = ("producto", "temperatura", "estado")
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": "Faltan campos requeridos", "campos": missing_fields}), 400

    product = data["producto"]
    if not isinstance(product, str) or product not in PRODUCT_PROFILES:
        return jsonify({
            "error": (
                "producto debe ser Refrigerados, Frutas_Verduras, Prueba, "
                "FrutasVerduras, Testeo o Congelados"
            )
        }), 400

    raw_temperature = data["temperatura"]
    if isinstance(raw_temperature, bool) or not isinstance(raw_temperature, (int, float)):
        return jsonify({"error": "temperatura debe ser un número"}), 400
    temperature = float(raw_temperature)
    if not math.isfinite(temperature):
        return jsonify({"error": "temperatura debe ser un número finito"}), 400
    if not -55 <= temperature <= 125:
        return jsonify({"error": "temperatura fuera del rango del sensor DS18B20"}), 400

    expected_profile, minimum, maximum = PRODUCT_PROFILES[product]
    expected_state = "OPTIMO" if minimum <= temperature <= maximum else "ALERTA"
    if data["estado"] != expected_state:
        return jsonify({
            "error": "estado no coincide con la temperatura y el producto",
            "estado_esperado": expected_state,
        }), 400

    metadata_fields = ("tempMin", "tempMax", "perfil")
    supplied_metadata = [field in data for field in metadata_fields]
    if any(supplied_metadata) and not all(supplied_metadata):
        return jsonify({
            "error": "tempMin, tempMax y perfil deben enviarse juntos"
        }), 400

    temp_min = None
    temp_max = None
    profile = None
    if all(supplied_metadata):
        raw_min = data["tempMin"]
        raw_max = data["tempMax"]
        profile = data["perfil"]
        if (
            isinstance(raw_min, bool)
            or not isinstance(raw_min, (int, float))
            or isinstance(raw_max, bool)
            or not isinstance(raw_max, (int, float))
            or not math.isfinite(raw_min)
            or not math.isfinite(raw_max)
        ):
            return jsonify({"error": "tempMin y tempMax deben ser números finitos"}), 400
        if raw_min != minimum or raw_max != maximum:
            return jsonify({
                "error": "tempMin y tempMax no coinciden con el perfil del producto",
                "tempMin_esperado": minimum,
                "tempMax_esperado": maximum,
            }), 400
        if profile != expected_profile:
            return jsonify({
                "error": "perfil no coincide con el producto",
                "perfil_esperado": expected_profile,
            }), 400
        temp_min = float(raw_min)
        temp_max = float(raw_max)

    reading = LecturaTemperatura(
        producto=product,
        temperatura=temperature,
        estado=expected_state,
        temp_min=temp_min,
        temp_max=temp_max,
        perfil=profile,
        fecha_creacion=datetime.now(timezone.utc),
    )
    db.session.add(reading)
    db.session.commit()
    return jsonify(reading_to_dict(reading)), 201
