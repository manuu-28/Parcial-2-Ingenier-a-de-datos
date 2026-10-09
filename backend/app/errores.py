
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, OperationalError

# Mensajes para restricciones
MENSAJES_RESTRICCION = {
    "clientes_documento_key": "Ya existe un cliente con ese documento.",
    "asistentes_documento_key": "Ya existe un asistente con ese documento.",
    "staff_correo_key": "Ya existe un empleado con ese correo.",
    "salones_nombre_key": "Ya existe un salón con ese nombre.",
    "servicios_nombre_key": "Ya existe un servicio con ese nombre.",
    "uq_evento_servicio": "Ese servicio ya está contratado en el evento; modifíquelo con PUT.",
    "uq_inscripcion": "El asistente ya está inscrito en este evento.",
    "ck_eventos_fin_posterior": "La fecha/hora de fin debe ser posterior a la de inicio.",
    "ck_eventos_aforo": "El aforo esperado debe ser mayor que cero.",
    "ck_staff_no_es_su_propio_jefe": "Un empleado no puede ser su propio jefe.",
    "ck_clientes_correo": "El correo del cliente no es válido.",
    "ck_asistentes_correo": "El correo del asistente no es válido.",
}


def obtener_o_404(db, entidad, id_, nombre: str):
    obj = db.get(entidad, id_)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{nombre} {id_} no existe.")
    return obj


def _respuesta(status: int, detalle: str, regla: str, codigo=None, sugerencia=None):
    cuerpo = {"detail": detalle, "regla": regla}
    if codigo:
        cuerpo["codigo_sql"] = codigo
    if sugerencia:
        cuerpo["sugerencia"] = sugerencia
    return JSONResponse(status_code=status, content=cuerpo)


def registrar_manejadores(app: FastAPI) -> None:

    @app.exception_handler(OperationalError)
    async def base_no_disponible(request: Request, exc: OperationalError):
        return _respuesta(503, "La base de datos no está disponible en este momento.", "BASE_DE_DATOS")

    @app.exception_handler(DBAPIError)
    async def error_de_base(request: Request, exc: DBAPIError):
        orig = exc.orig                                   # error original de PostgreSQL (psycopg2)
        codigo = getattr(orig, "pgcode", None)
        diag = getattr(orig, "diag", None)
        mensaje = (getattr(diag, "message_primary", None) or str(orig)).strip()
        restriccion = getattr(diag, "constraint_name", None)

        if codigo == "P0001":                             # RAISE EXCEPTION de un trigger o función
            regla = mensaje.split(":", 1)[0] if ":" in mensaje else "REGLA"
            return _respuesta(409, mensaje, regla, codigo, getattr(diag, "message_hint", None))
        if codigo == "23505":
            return _respuesta(409, MENSAJES_RESTRICCION.get(restriccion, "Ya existe un registro con esos datos."),
                              "DUPLICADO", codigo)
        if codigo == "23503":
            return _respuesta(409, "El registro relacionado no existe o tiene datos que dependen de él.",
                              "REFERENCIA", codigo)
        if codigo in ("23514", "23502", "22P02", "22003", "22007", "22008"):
            return _respuesta(422, MENSAJES_RESTRICCION.get(restriccion, f"Datos inválidos: {mensaje}"),
                              "DATOS", codigo)
        return _respuesta(500, "Error inesperado en la base de datos.", "ERROR_INTERNO", codigo)

    @app.exception_handler(RequestValidationError)
    async def datos_invalidos(request: Request, exc: RequestValidationError):
        errores = []
        for e in exc.errors():
            campo = ".".join(str(p) for p in e["loc"] if p not in ("body", "query", "path"))
            msg = e["msg"].replace("Value error, ", "")
            errores.append(f"{campo}: {msg}" if campo else msg)
        return JSONResponse(status_code=422, content={"detail": "; ".join(errores), "regla": "VALIDACION",
                                                      "errores": errores})
