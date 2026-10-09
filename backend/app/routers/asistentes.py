"""Asistentes: listar/buscar, registrar y ver sus inscripciones."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.errores import obtener_o_404
from app.models import AsistenteEntity
from app.schemas import AsistenteCreate, AsistenteResponse

router = APIRouter()


@router.get("/", response_model=List[AsistenteResponse], summary="Listar o buscar asistentes")
def listar_asistentes(q: Optional[str] = Query(None, description="Busca en nombre, documento o empresa"),
                      db: Session = Depends(get_db)):
    consulta = db.query(AsistenteEntity)
    if q:
        patron = f"%{q}%"
        consulta = consulta.filter(or_(AsistenteEntity.nombre.ilike(patron),
                                       AsistenteEntity.documento.ilike(patron),
                                       AsistenteEntity.empresa.ilike(patron)))
    return consulta.order_by(AsistenteEntity.nombre).all()


@router.post("/", response_model=AsistenteResponse, status_code=201, summary="Registrar asistente")
def crear_asistente(datos: AsistenteCreate, db: Session = Depends(get_db)):
    nuevo = AsistenteEntity(**datos.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.get("/{asistente_id}", response_model=AsistenteResponse, summary="Consultar un asistente")
def obtener_asistente(asistente_id: int, db: Session = Depends(get_db)):
    return obtener_o_404(db, AsistenteEntity, asistente_id, "El asistente")
