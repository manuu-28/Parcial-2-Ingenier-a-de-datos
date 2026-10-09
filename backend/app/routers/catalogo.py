"""Catálogo: salones (con disponibilidad A5) y servicios."""
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.errores import obtener_o_404
from app.models import SalonEntity, ServicioEntity
from app.schemas import SalonDisponible, SalonEstado, SalonResponse, ServicioResponse, ServicioUpdate

router_salones = APIRouter()
router_servicios = APIRouter()


@router_salones.get("/", response_model=List[SalonResponse], summary="Listar salones")
def listar_salones(solo_activos: bool = False, db: Session = Depends(get_db)):
    consulta = db.query(SalonEntity)
    if solo_activos:
        consulta = consulta.filter(SalonEntity.activo.is_(True))
    return consulta.order_by(SalonEntity.capacidad).all()


# Va antes de /{salon_id} para que "disponibles" no se confunda con un id
@router_salones.get("/disponibles", response_model=List[SalonDisponible],
                    summary="Salones disponibles (función A5)")
def salones_disponibles(inicio: datetime = Query(..., examples=["2026-11-18T09:00"]),
                        fin: datetime = Query(..., examples=["2026-11-18T11:00"]),
                        aforo: int = Query(..., gt=0),
                        excluir_evento: Optional[int] = Query(None, description="Al reprogramar, el propio evento"),
                        db: Session = Depends(get_db)):
    filas = db.execute(
        text("SELECT * FROM fn_salones_disponibles(:inicio, :fin, :aforo, :excluir)"),
        {"inicio": inicio, "fin": fin, "aforo": aforo, "excluir": excluir_evento},
    ).mappings().all()
    return [dict(f) for f in filas]


@router_salones.get("/{salon_id}", response_model=SalonResponse, summary="Consultar un salón")
def obtener_salon(salon_id: int, db: Session = Depends(get_db)):
    return obtener_o_404(db, SalonEntity, salon_id, "El salón")


@router_salones.patch("/{salon_id}", response_model=SalonResponse, summary="Habilitar o deshabilitar un salón")
def cambiar_estado_salon(salon_id: int, datos: SalonEstado, db: Session = Depends(get_db)):
    salon = obtener_o_404(db, SalonEntity, salon_id, "El salón")
    salon.activo = datos.activo
    db.commit()
    db.refresh(salon)
    return salon


@router_servicios.get("/", response_model=List[ServicioResponse], summary="Listar servicios del catálogo")
def listar_servicios(categoria: Optional[str] = None, db: Session = Depends(get_db)):
    consulta = db.query(ServicioEntity)
    if categoria:
        consulta = consulta.filter(ServicioEntity.categoria == categoria)
    return consulta.order_by(ServicioEntity.id).all()


@router_servicios.patch("/{servicio_id}", response_model=ServicioResponse,
                        summary="Cambiar precio o disponibilidad (los eventos ya cotizados no cambian)")
def actualizar_servicio(servicio_id: int, datos: ServicioUpdate, db: Session = Depends(get_db)):
    servicio = obtener_o_404(db, ServicioEntity, servicio_id, "El servicio")
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(servicio, campo, valor)
    db.commit()
    db.refresh(servicio)
    return servicio
