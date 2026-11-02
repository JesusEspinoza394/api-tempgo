from datetime import datetime, timezone
import math

from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import LecturaTemperatura

telemetry_bp = Blueprint("telemetry", __name__)

PRODUCT_RANGES = {
    "Refrigerados": (0, 4),
    "FrutasVerduras": (8, 12),
    "Congelados": (-22, -16),
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

        results = db.session.scalars(
            db.select(LecturaTemperatura)
            .order_by(
                LecturaTemperatura.fecha_creacion.desc(),
                LecturaTemperatura.id.desc(),
            )
            .limit(limit)
        ).all()
        return jsonify([reading_to_dict(item) for item in results])

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "El cuerpo debe ser un objeto JSON"}), 400

    required_fields = ("producto", "temperatura", "estado")
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        return jsonify({"error": "Faltan campos requeridos", "campos": missing_fields}), 400

    product = data["producto"]
    if not isinstance(product, str) or product not in PRODUCT_RANGES:
        return jsonify({
            "error": "producto debe ser Refrigerados, FrutasVerduras o Congelados"
        }), 400

    raw_temperature = data["temperatura"]
    if isinstance(raw_temperature, bool) or not isinstance(raw_temperature, (int, float)):
        return jsonify({"error": "temperatura debe ser un número"}), 400
    temperature = float(raw_temperature)
    if not math.isfinite(temperature):
        return jsonify({"error": "temperatura debe ser un número finito"}), 400
    if not -55 <= temperature <= 125:
        return jsonify({"error": "temperatura fuera del rango del sensor DS18B20"}), 400

    minimum, maximum = PRODUCT_RANGES[product]
    expected_state = "OPTIMO" if minimum <= temperature <= maximum else "ALERTA"
    if data["estado"] != expected_state:
        return jsonify({
            "error": "estado no coincide con la temperatura y el producto",
            "estado_esperado": expected_state,
        }), 400

    reading = LecturaTemperatura(
        producto=product,
        temperatura=temperature,
        estado=expected_state,
        fecha_creacion=datetime.now(timezone.utc),
    )
    db.session.add(reading)
    db.session.commit()
    return jsonify(reading_to_dict(reading)), 201
