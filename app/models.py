from datetime import datetime

from .extensions import db


class AlimentoBase(db.Model):
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    alimento_especifico = db.Column(db.String(100), nullable=False)
    temperatura = db.Column(db.Float, nullable=False)
    rango = db.Column(db.String(100), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class AlimentoCongelado(AlimentoBase):
    __tablename__ = "alimentos_congelados"


class AlimentoRefrigerado(AlimentoBase):
    __tablename__ = "alimentos_refrigerados"


class AlimentoVerdura(AlimentoBase):
    __tablename__ = "alimentos_verduras"


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False, unique=True)
    edad = db.Column(db.Integer, nullable=True)
    password_hash = db.Column(db.String(255), nullable=True)
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
