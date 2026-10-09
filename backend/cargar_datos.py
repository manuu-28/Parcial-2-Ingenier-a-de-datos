
from pathlib import Path

from app.database import engine

script = (Path(__file__).parent / "sql" / "04_datos_prueba.sql").read_text(encoding="utf-8")
conexion = engine.raw_connection()
try:
    with conexion.cursor() as cursor:
        cursor.execute(script)
    conexion.commit()
    for aviso in conexion.notices:
        if "Carga" in aviso or "Ya hay" in aviso:
            print(aviso.strip())
finally:
    conexion.close()
