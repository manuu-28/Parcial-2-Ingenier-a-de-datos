from datetime import date, time, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

from api_cliente import barra_lateral, get, pesos, tabla, unir

st.set_page_config(page_title="Disponibilidad · NexoEventos", page_icon="🏛️", layout="wide")
barra_lateral()
st.title("🏛️ Disponibilidad de salones")
st.caption("Solo se muestran salones activos, con capacidad suficiente y sin cruces, "
           "dejando 1 hora de montaje entre eventos.")

c1, c2, c3, c4 = st.columns(4)
fecha = c1.date_input("Fecha", date.today() + timedelta(days=7))
h_ini = c2.time_input("Hora inicio", time(9, 0), step=1800)
h_fin = c3.time_input("Hora fin", time(11, 0), step=1800, help="Si es menor que el inicio, se toma del día siguiente")
aforo = c4.number_input("Personas", min_value=1, value=50, step=5)

fecha_fin = fecha + timedelta(days=1) if h_fin <= h_ini else fecha
if h_fin <= h_ini:
    st.caption(f"El evento termina el {fecha_fin:%Y-%m-%d} (después de medianoche).")

if st.button("Consultar", type="primary"):
    filas = get("/salones/disponibles", {"inicio": unir(fecha, h_ini), "fin": unir(fecha_fin, h_fin), "aforo": aforo})
    if filas is not None:
        if not filas:
            st.warning("No hay salones disponibles con esas condiciones.")
        else:
            st.success(f"{len(filas)} salón(es) disponible(s). El primero es el más ajustado al aforo.")
            for f in filas:
                f["precio"] = pesos(f["precio_hora"])
                f["costo"] = pesos(f["costo_estimado"])
            tabla(filas, {"nombre": "Salón", "tamano": "Tamaño", "capacidad": "Capacidad",
                          "precio": "Precio/hora", "costo": "Costo del salón"})
            fig = px.bar(pd.DataFrame(filas), x="nombre", y="costo_estimado", text="capacidad",
                         labels={"nombre": "Salón", "costo_estimado": "Costo del salón (COP)"})
            fig.update_traces(texttemplate="%{text} pers.")
            st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("Catálogo de salones")
salones = get("/salones/") or []
for s in salones:
    s["precio"] = pesos(s["precio_hora"])
    s["estado"] = "Activo" if s["activo"] else "Deshabilitado"
tabla(salones, {"nombre": "Salón", "tamano": "Tamaño", "capacidad": "Capacidad", "precio": "Precio/hora",
                "estado": "Estado"})
