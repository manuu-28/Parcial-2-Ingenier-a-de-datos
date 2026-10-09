
from sqlalchemy import (
    Boolean, CheckConstraint, Column, Computed, Date, DateTime, ForeignKey,
    Integer, Numeric, String, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from .database import Base

TIPOS_CLIENTE = ("Empresa", "Persona")
TAMANOS = ("Pequeño", "Mediano", "Grande")
CATEGORIAS = ("Bebidas", "Refrigerios", "Audiovisuales")
UNIDADES = ("Por persona", "Por hora", "Por unidad")
AREAS = ("Dirección", "Operaciones", "Comercial", "Logística", "Alimentos y Bebidas", "Audiovisuales")
TIPOS_EVENTO = ("Congreso", "Conferencia", "Feria", "Seminario", "Corporativo", "Social")
ESTADOS = ("Cotizado", "Confirmado", "Finalizado", "Cancelado")


def _en(valores):
    """Arma el texto de un CHECK ... IN (...)."""
    return "(" + ", ".join(f"'{v}'" for v in valores) + ")"


class ClienteEntity(Base):
    __tablename__ = "clientes"
    id = Column(Integer, primary_key=True)
    tipo = Column(String(10), nullable=False)                 # Empresa (NIT) o Persona (cédula)
    documento = Column(String(20), nullable=False, unique=True)
    nombre = Column(String(150), nullable=False)               # nombre o razón social
    correo = Column(String(120), nullable=False)
    telefono = Column(String(20), nullable=False)
    fecha_registro = Column(Date, nullable=False, server_default=func.current_date())

    eventos = relationship("EventoEntity", back_populates="cliente")

    __table_args__ = (
        CheckConstraint(f"tipo IN {_en(TIPOS_CLIENTE)}", name="ck_clientes_tipo"),
        CheckConstraint("correo LIKE '%_@_%'", name="ck_clientes_correo"),
    )


class SalonEntity(Base):
    __tablename__ = "salones"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(60), nullable=False, unique=True)
    tamano = Column(String(10), nullable=False)
    capacidad = Column(Integer, nullable=False)
    precio_hora = Column(Numeric(14, 2), nullable=False)
    activo = Column(Boolean, nullable=False, server_default="true")   # false = en mantenimiento

    __table_args__ = (
        CheckConstraint(f"tamano IN {_en(TAMANOS)}", name="ck_salones_tamano"),
        CheckConstraint("capacidad > 0", name="ck_salones_capacidad"),
        CheckConstraint("precio_hora > 0", name="ck_salones_precio"),
    )


class ServicioEntity(Base):
    __tablename__ = "servicios"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(80), nullable=False, unique=True)
    categoria = Column(String(20), nullable=False)
    unidad_cobro = Column(String(15), nullable=False)
    precio_unitario = Column(Numeric(14, 2), nullable=False)
    activo = Column(Boolean, nullable=False, server_default="true")

    __table_args__ = (
        CheckConstraint(f"categoria IN {_en(CATEGORIAS)}", name="ck_servicios_categoria"),
        CheckConstraint(f"unidad_cobro IN {_en(UNIDADES)}", name="ck_servicios_unidad"),
        CheckConstraint("precio_unitario > 0", name="ck_servicios_precio"),
    )


class StaffEntity(Base):
    __tablename__ = "staff"
    id = Column(Integer, primary_key=True)
    nombre = Column(String(120), nullable=False)
    cargo = Column(String(80), nullable=False)
    area = Column(String(25), nullable=False)
    correo = Column(String(120), nullable=False, unique=True)
    fecha_ingreso = Column(Date, nullable=False)
    jefe_id = Column(Integer, ForeignKey("staff.id"), nullable=True)   # auto-referencia; NULL = dirección general

    jefe = relationship("StaffEntity", remote_side=[id], back_populates="subordinados")
    subordinados = relationship("StaffEntity", back_populates="jefe")

    __table_args__ = (
        CheckConstraint(f"area IN {_en(AREAS)}", name="ck_staff_area"),
        CheckConstraint("jefe_id IS NULL OR jefe_id <> id", name="ck_staff_no_es_su_propio_jefe"),
    )


class EventoEntity(Base):
    __tablename__ = "eventos"
    id = Column(Integer, primary_key=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    salon_id = Column(Integer, ForeignKey("salones.id"), nullable=False)
    coordinador_id = Column(Integer, ForeignKey("staff.id"), nullable=True)   # obligatorio para confirmar (trigger A4)
    nombre = Column(String(150), nullable=False)
    tipo = Column(String(15), nullable=False)
    inicio = Column(DateTime, nullable=False)
    fin = Column(DateTime, nullable=False)                     # puede ser del día siguiente
    aforo_esperado = Column(Integer, nullable=False)
    estado = Column(String(12), nullable=False, server_default="Cotizado")
    valor_total = Column(Numeric(16, 2), nullable=False, server_default="0")   # lo calcula el trigger A3
    tasa_asistencia = Column(Numeric(5, 2), nullable=True)                      # la calcula el trigger A4
    fecha_creacion = Column(DateTime, nullable=False, server_default=func.localtimestamp())

    cliente = relationship("ClienteEntity", back_populates="eventos")
    salon = relationship("SalonEntity")
    coordinador = relationship("StaffEntity")
    servicios = relationship("EventoServicioEntity", back_populates="evento")
    inscripciones = relationship("InscripcionEntity", back_populates="evento")

    __table_args__ = (
        CheckConstraint(f"tipo IN {_en(TIPOS_EVENTO)}", name="ck_eventos_tipo"),
        CheckConstraint(f"estado IN {_en(ESTADOS)}", name="ck_eventos_estado"),
        CheckConstraint("fin > inicio", name="ck_eventos_fin_posterior"),
        CheckConstraint("aforo_esperado > 0", name="ck_eventos_aforo"),
        CheckConstraint("valor_total >= 0", name="ck_eventos_valor"),
        CheckConstraint("tasa_asistencia IS NULL OR tasa_asistencia BETWEEN 0 AND 100", name="ck_eventos_tasa"),
    )


class EventoServicioEntity(Base):
    """Servicios contratados por evento (tabla intermedia N:M con precio congelado)."""
    __tablename__ = "evento_servicios"
    id = Column(Integer, primary_key=True)
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False)
    servicio_id = Column(Integer, ForeignKey("servicios.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)                 # si llega vacía, la calcula el trigger A3
    cantidad_automatica = Column(Boolean, nullable=False, server_default="false")
    precio_unitario = Column(Numeric(14, 2), nullable=False)   # precio congelado al contratar (trigger A3)
    subtotal = Column(Numeric(16, 2), Computed("cantidad * precio_unitario", persisted=True))

    evento = relationship("EventoEntity", back_populates="servicios")
    servicio = relationship("ServicioEntity")

    __table_args__ = (
        UniqueConstraint("evento_id", "servicio_id", name="uq_evento_servicio"),
        CheckConstraint("cantidad > 0", name="ck_es_cantidad"),
        CheckConstraint("precio_unitario > 0", name="ck_es_precio"),
    )


class AsistenteEntity(Base):
    __tablename__ = "asistentes"
    id = Column(Integer, primary_key=True)
    documento = Column(String(20), nullable=False, unique=True)
    nombre = Column(String(120), nullable=False)
    correo = Column(String(120), nullable=False)
    empresa = Column(String(150), nullable=True)

    inscripciones = relationship("InscripcionEntity", back_populates="asistente")

    __table_args__ = (CheckConstraint("correo LIKE '%_@_%'", name="ck_asistentes_correo"),)


class InscripcionEntity(Base):
    """Inscripción de un asistente a un evento; fecha_checkin es la asistencia real."""
    __tablename__ = "inscripciones"
    id = Column(Integer, primary_key=True)
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False)
    asistente_id = Column(Integer, ForeignKey("asistentes.id"), nullable=False)
    fecha_inscripcion = Column(DateTime, nullable=False, server_default=func.localtimestamp())
    fecha_checkin = Column(DateTime, nullable=True)            # NULL = no ha llegado

    evento = relationship("EventoEntity", back_populates="inscripciones")
    asistente = relationship("AsistenteEntity", back_populates="inscripciones")

    __table_args__ = (UniqueConstraint("evento_id", "asistente_id", name="uq_inscripcion"),)


class AuditoriaEventoEntity(Base):
    __tablename__ = "auditoria_eventos"
    id = Column(Integer, primary_key=True)
    evento_id = Column(Integer, ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False)
    campo = Column(String(20), nullable=False)
    valor_anterior = Column(String(150), nullable=True)
    valor_nuevo = Column(String(150), nullable=True)
    usuario = Column(String(60), nullable=False)               # usuario de la APP (X-Usuario)
    fecha = Column(DateTime, nullable=False, server_default=func.localtimestamp())

    __table_args__ = (
        CheckConstraint("campo IN ('creacion', 'estado', 'salon', 'inicio', 'fin')", name="ck_auditoria_campo"),
    )
