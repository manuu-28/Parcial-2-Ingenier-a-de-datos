from datetime import date, datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

TipoCliente = Literal["Empresa", "Persona"]
Area = Literal["Dirección", "Operaciones", "Comercial", "Logística", "Alimentos y Bebidas", "Audiovisuales"]
TipoEvento = Literal["Congreso", "Conferencia", "Feria", "Seminario", "Corporativo", "Social"]
EstadoDestino = Literal["Confirmado", "Finalizado", "Cancelado"]

CORREO = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
MSG_FIN = "La fecha/hora de fin debe ser posterior a la de inicio"


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# Clientes
class ClienteCreate(BaseModel):
    tipo: TipoCliente = Field(..., description="Empresa (NIT) o Persona (cédula)")
    documento: str = Field(..., min_length=5, max_length=20, pattern=r"^[0-9\-]+$")
    nombre: str = Field(..., min_length=3, max_length=150)
    correo: str = Field(..., max_length=120, pattern=CORREO)
    telefono: str = Field(..., min_length=7, max_length=20, pattern=r"^[0-9+ ]+$")


class ClienteResponse(ORM):
    id: int
    tipo: str
    documento: str
    nombre: str
    correo: str
    telefono: str
    fecha_registro: date


# Staff
class StaffCreate(BaseModel):
    nombre: str = Field(..., min_length=3, max_length=120)
    cargo: str = Field(..., min_length=3, max_length=80)
    area: Area
    correo: str = Field(..., max_length=120, pattern=CORREO)
    fecha_ingreso: date
    jefe_id: Optional[int] = Field(None, description="Jefe inmediato; vacío solo para la dirección general")


class StaffResponse(ORM):
    id: int
    nombre: str
    cargo: str
    area: str
    correo: str
    fecha_ingreso: date
    jefe_id: Optional[int] = None


# Catálogo
class SalonResponse(ORM):
    id: int
    nombre: str
    tamano: str
    capacidad: int
    precio_hora: float
    activo: bool


class SalonEstado(BaseModel):
    activo: bool = Field(..., description="false = deshabilitado por mantenimiento")


class SalonDisponible(BaseModel):
    salon_id: int
    nombre: str
    tamano: str
    capacidad: int
    precio_hora: float
    costo_estimado: float


class ServicioResponse(ORM):
    id: int
    nombre: str
    categoria: str
    unidad_cobro: str
    precio_unitario: float
    activo: bool


class ServicioUpdate(BaseModel):
    precio_unitario: Optional[Decimal] = Field(None, gt=0, max_digits=14, decimal_places=2)
    activo: Optional[bool] = None


# Eventos
class EventoCreate(BaseModel):
    cliente_id: int
    salon_id: int
    coordinador_id: Optional[int] = Field(None, description="Obligatorio para confirmar el evento")
    nombre: str = Field(..., min_length=3, max_length=150)
    tipo: TipoEvento
    inicio: datetime
    fin: datetime
    aforo_esperado: int = Field(..., gt=0)

    @model_validator(mode="after")
    def validar_horario(self):
        if self.fin <= self.inicio:
            raise ValueError(MSG_FIN)
        return self


class EventoReprogramar(BaseModel):
    """Solo se envían los campos que cambian."""
    salon_id: Optional[int] = None
    inicio: Optional[datetime] = None
    fin: Optional[datetime] = None
    aforo_esperado: Optional[int] = Field(None, gt=0)
    coordinador_id: Optional[int] = None

    @model_validator(mode="after")
    def validar(self):
        if not self.model_fields_set:
            raise ValueError("Indique al menos un campo para reprogramar")
        if self.inicio and self.fin and self.fin <= self.inicio:
            raise ValueError(MSG_FIN)
        return self


class EventoEstado(BaseModel):
    estado: EstadoDestino


class EventoResponse(ORM):
    id: int
    cliente_id: int
    salon_id: int
    coordinador_id: Optional[int] = None
    nombre: str
    tipo: str
    inicio: datetime
    fin: datetime
    aforo_esperado: int
    estado: str
    valor_total: float
    tasa_asistencia: Optional[float] = None


class EventoServicioCreate(BaseModel):
    servicio_id: int
    cantidad: Optional[int] = Field(None, gt=0, description="Vacía = aforo (por persona) u horas (por hora)")


class EventoServicioUpdate(BaseModel):
    cantidad: Optional[int] = Field(None, gt=0, description="Vacía = volver a la cantidad automática")


class EventoServicioResponse(BaseModel):
    servicio_id: int
    servicio: str
    unidad_cobro: str
    cantidad: int
    cantidad_automatica: bool
    precio_unitario: float
    subtotal: float
    valor_total_evento: Optional[float] = None


class ResumenAsistencia(BaseModel):
    aforo_esperado: int
    inscritos: int
    llegaron: int
    cupos_libres: int
    tasa_asistencia: Optional[float] = None


class EventoDetalle(EventoResponse):
    cliente: str
    salon: str
    coordinador: Optional[str] = None
    servicios: List[EventoServicioResponse]
    asistencia: ResumenAsistencia


class LineaCotizacion(BaseModel):
    concepto: str
    unidad: str
    cantidad: float
    precio_unitario: float
    subtotal: float


class Cotizacion(BaseModel):
    evento_id: int
    evento: str
    estado: str
    lineas: List[LineaCotizacion]
    total: float
    valor_total_en_base: float


class AuditoriaResponse(ORM):
    id: int
    campo: str
    valor_anterior: Optional[str] = None
    valor_nuevo: Optional[str] = None
    usuario: str
    fecha: datetime


# Asistentes
class AsistenteCreate(BaseModel):
    documento: str = Field(..., min_length=5, max_length=20, pattern=r"^[0-9A-Za-z\-]+$")
    nombre: str = Field(..., min_length=3, max_length=120)
    correo: str = Field(..., max_length=120, pattern=CORREO)
    empresa: Optional[str] = Field(None, max_length=150)


class AsistenteResponse(ORM):
    id: int
    documento: str
    nombre: str
    correo: str
    empresa: Optional[str] = None


class InscripcionCreate(BaseModel):
    documento: str = Field(..., description="Documento del asistente ya registrado")


class InscripcionResponse(BaseModel):
    id: int
    asistente_id: int
    documento: str
    nombre: str
    empresa: Optional[str] = None
    fecha_inscripcion: datetime
    fecha_checkin: Optional[datetime] = None


class CheckinCreate(BaseModel):
    documento: str
    fecha_hora: Optional[datetime] = Field(None, description="Vacía = hora actual del servidor de base de datos")
