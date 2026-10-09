
from sqlalchemy import text

from app import models  
from app.database import Base, engine
from main import aplicar_scripts_sql

with engine.begin() as conexion:
    conexion.execute(text("DROP SCHEMA public CASCADE"))
    conexion.execute(text("CREATE SCHEMA public"))

Base.metadata.create_all(bind=engine)
aplicar_scripts_sql()

import cargar_datos 
print("Base reiniciada con los datos de prueba.")
