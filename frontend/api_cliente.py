
import os
from datetime import date, datetime, time

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://127.0.0.1:8000")


def _llamar(metodo: str, ruta: str, **kwargs):
    """Devuelve (ok, datos). Nunca lanza excepción hacia la página."""
    try:
        r = requests.request(metodo, API_URL + ruta, timeout=20,
                             headers={"X-Usuario": st.session_state.get("usuario", "recepcion")}, **kwargs)
    except requests.ConnectionError:
        return False, {"detail": f"No hay conexión con la API ({API_URL}). Verifique que esté encendida.",
                       "regla": "API NO DISPONIBLE"}
    except requests.Timeout:
        return False, {"detail": "La API tardó demasiado en responder.", "regla": "API NO DISPONIBLE"}
    if r.status_code == 204:
        return True, None
    try:
        datos = r.json()
    except ValueError:
        datos = {"detail": r.text or f"Respuesta inesperada ({r.status_code})"}
    if not r.ok and isinstance(datos, dict):
        datos.setdefault("regla", {404: "NO ENCONTRADO", 409: "REGLA DE NEGOCIO", 422: "DATOS INVÁLIDOS"}
                         .get(r.status_code, f"ERROR {r.status_code}"))
        datos["status"] = r.status_code
    return r.ok, datos


def mostrar_error(datos: dict) -> None:
    regla = datos.get("regla", "ERROR")
    detalle = datos.get("detail", "Error desconocido")
    if isinstance(detalle, list):                       # por si llega el formato estándar de FastAPI
        detalle = "; ".join(str(d.get("msg", d)) for d in detalle)
    if isinstance(detalle, str) and detalle.upper().startswith(f"{regla.upper()}:"):
        detalle = detalle[len(regla) + 1:].strip()      # evita "CUPO — CUPO: ..."
    icono = "🔌" if regla == "API NO DISPONIBLE" else "⛔"
    st.error(f"{icono} **{regla}** — {detalle}")
    if datos.get("sugerencia"):
        st.info(f"💡 {datos['sugerencia']}")


def get(ruta: str, params: dict = None):
    """GET: devuelve los datos o None (y muestra el error)."""
    ok, datos = _llamar("GET", ruta, params={k: v for k, v in (params or {}).items() if v not in (None, "")})
    if not ok:
        mostrar_error(datos)
        return None
    return datos


def enviar(metodo: str, ruta: str, json: dict = None, exito: str = "Operación realizada."):
    """POST/PUT/PATCH/DELETE: muestra éxito o la regla violada. Devuelve (ok, datos)."""
    ok, datos = _llamar(metodo, ruta, json=json)
    if ok:
        st.success(f"✅ {exito}")
    else:
        mostrar_error(datos)
    return ok, datos


def barra_lateral() -> None:
    st.sidebar.markdown("### 🏛️ Centro de Convenciones Nexo")
    st.session_state["usuario"] = st.sidebar.text_input(
        "Usuario de la aplicación", value=st.session_state.get("usuario", "recepcion"),
        help="Se envía en el encabezado X-Usuario y queda en la auditoría de cada cambio.")
    ok, _ = _llamar("GET", "/")
    st.sidebar.caption(f"API: {API_URL} {'🟢 en línea' if ok else '🔴 sin conexión'}")


# ----------------------------------------------------------------- utilidades de formato
def pesos(valor) -> str:
    return "—" if valor is None else f"$ {float(valor):,.0f}".replace(",", ".")


def unir(fecha: date, hora: time) -> str:
    return datetime.combine(fecha, hora).isoformat(timespec="minutes")


def tabla(datos, columnas: dict = None, **kwargs):
    """Muestra una lista de diccionarios como tabla, con columnas renombradas."""
    if not datos:
        st.caption("Sin registros.")
        return
    df = pd.DataFrame(datos)
    if columnas:
        df = df[[c for c in columnas if c in df.columns]].rename(columns=columnas)
    st.dataframe(df, width="stretch", hide_index=True, **kwargs)


def etiqueta_evento(e: dict) -> str:
    return f"#{e['id']} · {e['nombre']} · {e['inicio'][:16].replace('T', ' ')} · {e['estado']}"
