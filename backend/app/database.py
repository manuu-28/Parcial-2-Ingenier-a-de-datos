import os

from dotenv import load_dotenv
from fastapi import Header
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("Falta la variable DATABASE_URL. Cree el archivo .env (ver .env.example).")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(SessionLocal, "after_begin")
def _enviar_usuario_a_postgres(session, transaction, connection):
    """Al iniciar cada transacción, entrega el usuario de la app a la base (pista A4)."""
    usuario = session.info.get("usuario", "anonimo")
    # true = el valor solo vive dentro de esta transacción
    connection.execute(text("SELECT set_config('nexo.usuario', :u, true)"), {"u": usuario})


def get_db(x_usuario: str = Header(default="anonimo", description="Usuario de la aplicación que hace la operación")):
    """Dependencia de FastAPI: entrega una sesión con el usuario de la app ya asignado."""
    db = SessionLocal()
    db.info["usuario"] = x_usuario
    try:
        yield db
    finally:
        db.close()
