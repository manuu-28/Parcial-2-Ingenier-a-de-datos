
import pandas as pd
import plotly.express as px
import streamlit as st

from api_cliente import barra_lateral, get, pesos, tabla

st.set_page_config(page_title="NexoEventos", layout="wide")
barra_lateral()

st.title("NexoEventos · Tablero")

datos = get("/reportes/tablero")
if datos:
    c1, c2, c3, c4 = st.columns(4)
    total = sum(x["cantidad"] for x in datos["por_estado"])
    c1.metric("Eventos registrados", total)
    c2.metric("Eventos finalizados", datos["finalizados"])
    c3.metric("Tasa de asistencia promedio",
              "—" if datos["tasa_promedio"] is None else f"{datos['tasa_promedio']:.2f} %")
    c4.metric("Facturación (no cancelados)", pesos(datos["facturacion"]))

    izq, der = st.columns([1, 2])
    with izq:
        st.subheader("Eventos por estado")
        if datos["por_estado"]:
            df = pd.DataFrame(datos["por_estado"])
            fig = px.pie(df, names="estado", values="cantidad", hole=0.45,
                         color="estado", color_discrete_map={"Cotizado": "#94a3b8", "Confirmado": "#2563eb",
                                                             "Finalizado": "#16a34a", "Cancelado": "#dc2626"})
            fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig, width="stretch")
    with der:
        st.subheader("Próximos eventos")
        for p in datos["proximos"]:
            p["inicio"] = p["inicio"][:16].replace("T", " ")
            p["valor_total"] = pesos(p["valor_total"])
            p["ocupacion"] = f"{p['inscritos']}/{p['aforo_esperado']}"
        tabla(datos["proximos"], {"id": "Id", "nombre": "Evento", "inicio": "Inicio", "salon": "Salón",
                                  "cliente": "Cliente", "estado": "Estado", "ocupacion": "Inscritos/aforo",
                                  "valor_total": "Valor"})

st.caption("Use el menú de la izquierda para gestionar eventos, asistentes, disponibilidad, clientes, staff y reportes.")
