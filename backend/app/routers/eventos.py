"""
Eventos: crear, listar, detalle, reprogramar, cambiar estado, servicios,
cotización, auditoría, inscripciones y check-in.

Las reglas de negocio las aplica PostgreSQL (triggers). Aquí solo se valida
que los registros existan (404) y se hace db.refresh() después de cada commit
para traer lo que calcularon los triggers (valor_total, tasa_asistencia).
"""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.errores import obtener_o_404
from app.models import (
    AsistenteEntity, AuditoriaEventoEntity, ClienteEntity, EventoEntity, EventoServicioEntity,
    InscripcionEntity, SalonEntity, ServicioEntity, StaffEntity,
)
from app.schemas import (
    AuditoriaResponse, CheckinCreate, Cotizacion, EventoCreate, EventoDetalle, EventoEstado,
    EventoReprogramar, EventoResponse, EventoServicioCreate, EventoServicioResponse,
    EventoServicioUpdate, InscripcionCreate, InscripcionResponse,
)

router = APIRouter()


# ----------------------------------------------------------------- utilidades
def _evento(db: Session, evento_id: int) -> EventoEntity:
    return obtener_o_404(db, EventoEntity, evento_id, "El evento")


def _linea_servicio(es: EventoServicioEntity, valor_total=None) -> dict:
    return {
        "servicio_id": es.servicio_id,
        "servicio": es.servicio.nombre,
        "unidad_cobro": es.servicio.unidad_cobro,
        "cantidad": es.cantidad,
        "cantidad_automatica": es.cantidad_automatica,
        "precio_unitario": es.precio_unitario,
        "subtotal": es.subtotal,
        "valor_total_evento": valor_total,
    }


def _inscripcion(i: InscripcionEntity) -> dict:
    return {
        "id": i.id, "asistente_id": i.asistente_id, "documento": i.asistente.documento,
        "nombre": i.asistente.nombre, "empresa": i.asistente.empresa,
        "fecha_inscripcion": i.fecha_inscripcion, "fecha_checkin": i.fecha_checkin,
    }


def _validar_referencias(db: Session, salon_id=None, cliente_id=None, coordinador_id=None):
    if cliente_id is not None:
        obtener_o_404(db, ClienteEntity, cliente_id, "El cliente")
    if salon_id is not None:
        obtener_o_404(db, SalonEntity, salon_id, "El salón")
    if coordinador_id is not None:
        obtener_o_404(db, StaffEntity, coordinador_id, "El coordinador")


# ----------------------------------------------------------------- CRUD de eventos
@router.get("/", response_model=List[EventoResponse], summary="Listar eventos con filtros")
def listar_eventos(estado: Optional[str] = None,
                   cliente_id: Optional[int] = None,
                   salon_id: Optional[int] = None,
                   desde: Optional[datetime] = Query(None, description="Inicio mayor o igual a"),
                   hasta: Optional[datetime] = Query(None, description="Inicio menor o igual a"),
                   q: Optional[str] = Query(None, description="Busca en el nombre"),
                   db: Session = Depends(get_db)):
    consulta = db.query(EventoEntity)
    if estado:
        consulta = consulta.filter(EventoEntity.estado == estado)
    if cliente_id:
        consulta = consulta.filter(EventoEntity.cliente_id == cliente_id)
    if salon_id:
        consulta = consulta.filter(EventoEntity.salon_id == salon_id)
    if desde:
        consulta = consulta.filter(EventoEntity.inicio >= desde)
    if hasta:
        consulta = consulta.filter(EventoEntity.inicio <= hasta)
    if q:
        consulta = consulta.filter(EventoEntity.nombre.ilike(f"%{q}%"))
    return consulta.order_by(EventoEntity.inicio).all()


@router.post("/", response_model=EventoResponse, status_code=201, summary="Crear evento (nace Cotizado)")
def crear_evento(datos: EventoCreate, db: Session = Depends(get_db)):
    _validar_referencias(db, datos.salon_id, datos.cliente_id, datos.coordinador_id)
    nuevo = EventoEntity(**datos.model_dump())
    db.add(nuevo)
    db.commit()            # aquí actúan los triggers A1, A3 y A4
    db.refresh(nuevo)      # trae valor_total calculado por la base
    return nuevo


@router.get("/{evento_id}", response_model=EventoDetalle, summary="Detalle con servicios y asistencia")
def detalle_evento(evento_id: int, db: Session = Depends(get_db)):
    e = _evento(db, evento_id)
    resumen = db.execute(
        text("SELECT aforo_esperado, inscritos, llegaron, cupos_libres, tasa_asistencia "
             "FROM vw_asistencia_eventos WHERE evento_id = :id"), {"id": evento_id}).mappings().one()
    return {
        **EventoResponse.model_validate(e).model_dump(),
        "cliente": e.cliente.nombre,
        "salon": e.salon.nombre,
        "coordinador": e.coordinador.nombre if e.coordinador else None,
        "servicios": [_linea_servicio(es) for es in sorted(e.servicios, key=lambda x: x.servicio_id)],
        "asistencia": dict(resumen),
    }


@router.patch("/{evento_id}", response_model=EventoResponse, summary="Reprogramar: salón, horario, aforo")
def reprogramar_evento(evento_id: int, datos: EventoReprogramar, db: Session = Depends(get_db)):
    e = _evento(db, evento_id)
    cambios = datos.model_dump(exclude_unset=True)
    _validar_referencias(db, salon_id=cambios.get("salon_id"), coordinador_id=cambios.get("coordinador_id"))
    for campo, valor in cambios.items():
        setattr(e, campo, valor)
    db.commit()            # A1 vuelve a validar, A3 recalcula, A4 audita
    db.refresh(e)
    return e


@router.patch("/{evento_id}/estado", response_model=EventoResponse, summary="Confirmar, finalizar o cancelar")
def cambiar_estado(evento_id: int, datos: EventoEstado, db: Session = Depends(get_db)):
    e = _evento(db, evento_id)
    e.estado = datos.estado
    db.commit()            # A4 valida el cambio, calcula la tasa y audita
    db.refresh(e)
    return e


# ----------------------------------------------------------------- servicios del evento
@router.get("/{evento_id}/servicios", response_model=List[EventoServicioResponse],
            summary="Servicios contratados del evento")
def listar_servicios_evento(evento_id: int, db: Session = Depends(get_db)):
    e = _evento(db, evento_id)
    return [_linea_servicio(es) for es in sorted(e.servicios, key=lambda x: x.servicio_id)]


@router.post("/{evento_id}/servicios", response_model=EventoServicioResponse, status_code=201,
             summary="Agregar un servicio (precio congelado; cantidad automática si se omite)")
def agregar_servicio(evento_id: int, datos: EventoServicioCreate, db: Session = Depends(get_db)):
    e = _evento(db, evento_id)
    obtener_o_404(db, ServicioEntity, datos.servicio_id, "El servicio")
    # precio_unitario lo reemplaza el trigger por el del catálogo; se envía 1 solo para cumplir NOT NULL
    linea = EventoServicioEntity(evento_id=evento_id, servicio_id=datos.servicio_id,
                                 cantidad=datos.cantidad, precio_unitario=1)
    db.add(linea)
    db.commit()
    db.refresh(linea)
    db.refresh(e)
    return _linea_servicio(linea, e.valor_total)


def _buscar_linea(db: Session, evento_id: int, servicio_id: int) -> EventoServicioEntity:
    linea = (db.query(EventoServicioEntity)
             .filter_by(evento_id=evento_id, servicio_id=servicio_id).first())
    if linea is None:
        raise HTTPException(status_code=404, detail=f"El servicio {servicio_id} no está contratado en el evento {evento_id}.")
    return linea


@router.put("/{evento_id}/servicios/{servicio_id}", response_model=EventoServicioResponse,
            summary="Cambiar la cantidad de un servicio contratado")
def modificar_servicio(evento_id: int, servicio_id: int, datos: EventoServicioUpdate,
                       db: Session = Depends(get_db)):
    e = _evento(db, evento_id)
    linea = _buscar_linea(db, evento_id, servicio_id)
    linea.cantidad = datos.cantidad          # None = el trigger vuelve a calcularla
    db.commit()
    db.refresh(linea)
    db.refresh(e)
    return _linea_servicio(linea, e.valor_total)


@router.delete("/{evento_id}/servicios/{servicio_id}", status_code=204, summary="Quitar un servicio")
def quitar_servicio(evento_id: int, servicio_id: int, db: Session = Depends(get_db)):
    _evento(db, evento_id)
    db.delete(_buscar_linea(db, evento_id, servicio_id))
    db.commit()
    return Response(status_code=204)


# ----------------------------------------------------------------- cotización y auditoría
@router.get("/{evento_id}/cotizacion", response_model=Cotizacion, summary="Desglose: salón + servicios = total")
def cotizacion(evento_id: int, db: Session = Depends(get_db)):
    e = _evento(db, evento_id)
    salon = db.execute(
        text("SELECT s.nombre, ROUND(fn_horas(e.inicio, e.fin), 2) AS horas, s.precio_hora, "
             "ROUND(fn_horas(e.inicio, e.fin) * s.precio_hora, 2) AS subtotal "
             "FROM eventos e JOIN salones s ON s.id = e.salon_id WHERE e.id = :id"),
        {"id": evento_id}).mappings().one()
    lineas = [{"concepto": f"Alquiler {salon['nombre']}", "unidad": "Por hora", "cantidad": salon["horas"],
               "precio_unitario": salon["precio_hora"], "subtotal": salon["subtotal"]}]
    for es in sorted(e.servicios, key=lambda x: x.servicio_id):
        lineas.append({"concepto": es.servicio.nombre, "unidad": es.servicio.unidad_cobro,
                       "cantidad": es.cantidad, "precio_unitario": es.precio_unitario, "subtotal": es.subtotal})
    return {"evento_id": e.id, "evento": e.nombre, "estado": e.estado, "lineas": lineas,
            "total": round(sum(float(l["subtotal"]) for l in lineas), 2),
            "valor_total_en_base": e.valor_total}


@router.get("/{evento_id}/auditoria", response_model=List[AuditoriaResponse], summary="Historial de cambios")
def auditoria(evento_id: int, db: Session = Depends(get_db)):
    _evento(db, evento_id)
    return (db.query(AuditoriaEventoEntity).filter_by(evento_id=evento_id)
            .order_by(AuditoriaEventoEntity.fecha, AuditoriaEventoEntity.id).all())


# ----------------------------------------------------------------- inscripciones y check-in
def _asistente_por_documento(db: Session, documento: str) -> AsistenteEntity:
    a = db.query(AsistenteEntity).filter_by(documento=documento).first()
    if a is None:
        raise HTTPException(status_code=404, detail=f"No hay un asistente registrado con documento {documento}.")
    return a


@router.get("/{evento_id}/inscripciones", response_model=List[InscripcionResponse],
            summary="Inscritos del evento (y quiénes llegaron)")
def listar_inscripciones(evento_id: int,
                         llegaron: Optional[bool] = Query(None, description="true = solo con check-in"),
                         db: Session = Depends(get_db)):
    _evento(db, evento_id)
    consulta = db.query(InscripcionEntity).filter_by(evento_id=evento_id)
    if llegaron is True:
        consulta = consulta.filter(InscripcionEntity.fecha_checkin.isnot(None))
    elif llegaron is False:
        consulta = consulta.filter(InscripcionEntity.fecha_checkin.is_(None))
    return [_inscripcion(i) for i in consulta.order_by(InscripcionEntity.id).all()]


@router.post("/{evento_id}/inscripciones", response_model=InscripcionResponse, status_code=201,
             summary="Inscribir un asistente (A2 controla cupo y estado)")
def inscribir(evento_id: int, datos: InscripcionCreate, db: Session = Depends(get_db)):
    _evento(db, evento_id)
    asistente = _asistente_por_documento(db, datos.documento)
    nueva = InscripcionEntity(evento_id=evento_id, asistente_id=asistente.id)
    db.add(nueva)
    db.commit()
    db.refresh(nueva)
    return _inscripcion(nueva)


@router.post("/{evento_id}/checkin", response_model=InscripcionResponse,
             summary="Registrar la llegada real por documento (A2 controla ventana y doble ingreso)")
def checkin(evento_id: int, datos: CheckinCreate, db: Session = Depends(get_db)):
    _evento(db, evento_id)
    asistente = _asistente_por_documento(db, datos.documento)
    insc = db.query(InscripcionEntity).filter_by(evento_id=evento_id, asistente_id=asistente.id).first()
    if insc is None:
        raise HTTPException(status_code=404, detail=f"{asistente.nombre} no está inscrito en este evento.")
    insc.fecha_checkin = datos.fecha_hora or func.localtimestamp()
    db.commit()
    db.refresh(insc)
    return _inscripcion(insc)
