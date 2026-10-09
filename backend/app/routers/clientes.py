"""Clientes: listar/buscar, registrar, consultar y ver sus eventos."""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.errores import obtener_o_404
from app.models import ClienteEntity, EventoEntity
from app.schemas import ClienteCreate, ClienteResponse, EventoResponse

router = APIRouter()


@router.get("/", response_model=List[ClienteResponse], summary="Listar o buscar clientes")
def listar_clientes(q: Optional[str] = Query(None, description="Busca en nombre o documento"),
                    tipo: Optional[str] = Query(None, description="Empresa o Persona"),
                    db: Session = Depends(get_db)):
    consulta = db.query(ClienteEntity)
    if q:
        patron = f"%{q}%"
        consulta = consulta.filter(or_(ClienteEntity.nombre.ilike(patron), ClienteEntity.documento.ilike(patron)))
    if tipo:
        consulta = consulta.filter(ClienteEntity.tipo == tipo)
    return consulta.order_by(ClienteEntity.nombre).all()


@router.post("/", response_model=ClienteResponse, status_code=201, summary="Registrar cliente")
def crear_cliente(datos: ClienteCreate, db: Session = Depends(get_db)):
    nuevo = ClienteEntity(**datos.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.get("/{cliente_id}", response_model=ClienteResponse, summary="Consultar un cliente")
def obtener_cliente(cliente_id: int, db: Session = Depends(get_db)):
    return obtener_o_404(db, ClienteEntity, cliente_id, "El cliente")


@router.get("/{cliente_id}/eventos", response_model=List[EventoResponse], summary="Eventos de un cliente")
def eventos_del_cliente(cliente_id: int, db: Session = Depends(get_db)):
    obtener_o_404(db, ClienteEntity, cliente_id, "El cliente")
    return (db.query(EventoEntity).filter(EventoEntity.cliente_id == cliente_id)
            .order_by(EventoEntity.inicio.desc()).all())
