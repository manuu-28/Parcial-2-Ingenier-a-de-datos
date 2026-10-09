from datetime import datetime

import streamlit as st

from api_cliente import barra_lateral, enviar, etiqueta_evento, get, tabla, unir

st.set_page_config(page_title="Asistentes · NexoEventos", page_icon="🎟️", layout="wide")
barra_lateral()
st.title("🎟️ Asistentes y check-in")

eventos = get("/eventos/") or []
abiertos = [e for e in eventos if e["estado"] in ("Cotizado", "Confirmado")]

t_reg, t_insc, t_check, t_lista = st.tabs(["🧍 Registrar asistente", "📝 Inscribir", "🚪 Check-in en puerta",
                                           "👥 Inscritos y llegadas"])

with t_reg:
    with st.form("form_asistente", clear_on_submit=True):
        c1, c2 = st.columns(2)
        doc = c1.text_input("Documento")
        nom = c2.text_input("Nombre completo")
        c1, c2 = st.columns(2)
        cor = c1.text_input("Correo")
        emp = c2.text_input("Empresa (opcional)")
        if st.form_submit_button("Registrar asistente", type="primary"):
            enviar("POST", "/asistentes/", {"documento": doc, "nombre": nom, "correo": cor, "empresa": emp or None},
                   exito="Asistente registrado.")
    q = st.text_input("Buscar asistente (nombre, documento o empresa)")
    tabla(get("/asistentes/", {"q": q}) or [], {"documento": "Documento", "nombre": "Nombre",
                                                "correo": "Correo", "empresa": "Empresa"}, height=300)

with t_insc:
    if not abiertos:
        st.info("No hay eventos abiertos a inscripción.")
    else:
        ev = st.selectbox("Evento", abiertos, format_func=etiqueta_evento, key="ev_insc")
        doc = st.text_input("Documento del asistente", key="doc_insc")
        if st.button("Inscribir", type="primary"):
            ok, r = enviar("POST", f"/eventos/{ev['id']}/inscripciones", {"documento": doc},
                           exito="Asistente inscrito.")
            if ok:
                st.write(f"{r['nombre']} quedó inscrito en **{ev['nombre']}**.")

with t_check:
    st.caption("Se permite desde 1 hora antes del inicio hasta la hora de fin, y una sola vez por persona.")
    activos = [e for e in eventos if e["estado"] == "Confirmado"]
    if not activos:
        st.info("No hay eventos confirmados.")
    else:
        ev = st.selectbox("Evento", activos, format_func=etiqueta_evento, key="ev_check")
        doc = st.text_input("Documento del asistente", key="doc_check")
        manual = st.toggle("Indicar hora de llegada manualmente (para pruebas)")
        fecha_hora = None
        if manual:
            ini = datetime.fromisoformat(ev["inicio"])
            c1, c2 = st.columns(2)
            fecha_hora = unir(c1.date_input("Fecha", ini.date()), c2.time_input("Hora", ini.time(), step=300))
        if st.button("Registrar ingreso", type="primary"):
            ok, r = enviar("POST", f"/eventos/{ev['id']}/checkin", {"documento": doc, "fecha_hora": fecha_hora},
                           exito="Ingreso registrado.")
            if ok:
                st.write(f"Bienvenido(a), **{r['nombre']}** · {r['fecha_checkin'][:16].replace('T', ' ')}")

with t_lista:
    if eventos:
        ev = st.selectbox("Evento", eventos, format_func=etiqueta_evento, key="ev_lista")
        filtro = st.radio("Mostrar", ["Todos", "Llegaron", "No han llegado"], horizontal=True)
        llegaron = {"Todos": None, "Llegaron": True, "No han llegado": False}[filtro]
        det = get(f"/eventos/{ev['id']}")
        if det:
            a = det["asistencia"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Aforo", a["aforo_esperado"])
            c2.metric("Inscritos", a["inscritos"])
            c3.metric("Llegaron", a["llegaron"])
            c4.metric("Cupos libres", a["cupos_libres"])
        filas = get(f"/eventos/{ev['id']}/inscripciones", {"llegaron": llegaron}) or []
        for f in filas:
            f["checkin"] = f["fecha_checkin"][:16].replace("T", " ") if f["fecha_checkin"] else "—"
        tabla(filas, {"documento": "Documento", "nombre": "Nombre", "empresa": "Empresa", "checkin": "Llegada"})
