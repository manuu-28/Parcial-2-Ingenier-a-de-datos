"""Staff: listar y registrar empleados con su jefe inmediato."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.errores import obtener_o_404
from app.models import StaffEntity
from app.schemas import StaffCreate, StaffResponse

router = APIRouter()


@router.get("/", response_model=List[StaffResponse], summary="Listar staff")
def listar_staff(area: Optional[str] = None,
                 q: Optional[str] = Query(None, description="Busca en nombre o cargo"),
                 db: Session = Depends(get_db)):
    consulta = db.query(StaffEntity)
    if area:
        consulta = consulta.filter(StaffEntity.area == area)
    if q:
        consulta = consulta.filter(StaffEntity.nombre.ilike(f"%{q}%") | StaffEntity.cargo.ilike(f"%{q}%"))
    return consulta.order_by(StaffEntity.id).all()


@router.post("/", response_model=StaffResponse, status_code=201, summary="Registrar empleado con su jefe")
def crear_staff(datos: StaffCreate, db: Session = Depends(get_db)):
    if datos.jefe_id is not None:
        obtener_o_404(db, StaffEntity, datos.jefe_id, "El jefe")
    elif db.query(StaffEntity).filter(StaffEntity.jefe_id.is_(None)).count() > 0:
        raise HTTPException(status_code=422, detail="Solo la dirección general no tiene jefe; indique jefe_id.")
    nuevo = StaffEntity(**datos.model_dump())
    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)
    return nuevo


@router.get("/{staff_id}", response_model=StaffResponse, summary="Consultar un empleado")
def obtener_staff(staff_id: int, db: Session = Depends(get_db)):
    return obtener_o_404(db, StaffEntity, staff_id, "El empleado")
