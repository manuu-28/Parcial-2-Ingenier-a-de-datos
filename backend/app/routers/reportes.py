"""
Reportes B1 a B4 y tablero de inicio.
Cada uno llama a una función de PostgreSQL con SQL parametrizado (text + :parametros);
no se reescriben con el ORM.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.errores import obtener_o_404
from app.models import SalonEntity, StaffEntity

router = APIRouter()


def _filas(db: Session, sql: str, params: dict = None):
    return [dict(f) for f in db.execute(text(sql), params or {}).mappings().all()]


@router.get("/organigrama", summary="B1. Organigrama (CTE recursiva)")
def organigrama(staff_id: Optional[int] = Query(None, description="Vacío = toda la organización"),
                db: Session = Depends(get_db)):
    if staff_id is not None:
        obtener_o_404(db, StaffEntity, staff_id, "El empleado")
    return _filas(db, "SELECT * FROM fn_organigrama(:id)", {"id": staff_id})


@router.get("/escalamiento/{staff_id}", summary="B2. Cadena de escalamiento (CTE recursiva)")
def escalamiento(staff_id: int, db: Session = Depends(get_db)):
    obtener_o_404(db, StaffEntity, staff_id, "El empleado")
    return _filas(db, "SELECT * FROM fn_escalamiento(:id)", {"id": staff_id})


@router.get("/ranking-clientes", summary="B3. Ranking de clientes y Pareto (funciones de ventana)")
def ranking_clientes(db: Session = Depends(get_db)):
    return _filas(db, "SELECT * FROM fn_ranking_clientes()")


@router.get("/ocupacion-salones", summary="B4. Ocupación de salones y tiempos muertos (ventanas)")
def ocupacion_salones(salon_id: Optional[int] = Query(None, description="Vacío = todos los salones"),
                      db: Session = Depends(get_db)):
    if salon_id is not None:
        obtener_o_404(db, SalonEntity, salon_id, "El salón")
    return _filas(db, "SELECT * FROM fn_ocupacion_salones(:id)", {"id": salon_id})


@router.get("/tablero", summary="Tablero de inicio: eventos por estado, próximos y tasa promedio")
def tablero(db: Session = Depends(get_db)):
    por_estado = _filas(db, "SELECT estado, COUNT(*) AS cantidad FROM eventos GROUP BY estado ORDER BY estado")
    proximos = _filas(db, """
        SELECT e.id, e.nombre, e.estado, e.inicio, e.fin, s.nombre AS salon, c.nombre AS cliente,
               a.inscritos, e.aforo_esperado, e.valor_total
        FROM eventos e
        JOIN salones s ON s.id = e.salon_id
        JOIN clientes c ON c.id = e.cliente_id
        JOIN vw_asistencia_eventos a ON a.evento_id = e.id
        WHERE e.inicio >= LOCALTIMESTAMP AND e.estado <> 'Cancelado'
        ORDER BY e.inicio LIMIT :n""", {"n": 10})
    indicadores = db.execute(text("""
        SELECT ROUND(AVG(tasa_asistencia), 2)                                   AS tasa_promedio,
               COUNT(*) FILTER (WHERE estado = 'Finalizado')                    AS finalizados,
               COALESCE(SUM(valor_total) FILTER (WHERE estado <> 'Cancelado'), 0) AS facturacion
        FROM eventos""")).mappings().one()
    return {"por_estado": por_estado, "proximos": proximos, **dict(indicadores)}
