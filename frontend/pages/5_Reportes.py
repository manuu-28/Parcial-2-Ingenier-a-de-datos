import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

from api_cliente import barra_lateral, get, pesos, tabla

st.set_page_config(page_title="Reportes · NexoEventos", page_icon="📊", layout="wide")
barra_lateral()
st.title("📊 Reportes")

b1, b2, b3, b4 = st.tabs(["B1 · Organigrama", "B2 · Escalamiento", "B3 · Ranking y Pareto", "B4 · Ocupación de salones"])
staff = get("/staff/") or []

with b1:
    quien = st.selectbox("Desde", [None] + staff, key="b1",
                         format_func=lambda s: "Toda la organización" if s is None else f"{s['nombre']} · {s['cargo']}")
    filas = get("/reportes/organigrama", {"staff_id": quien["id"] if quien else None}) or []
    if filas:
        base = min(f["nivel"] for f in filas)
        for f in filas:
            f["persona"] = "    " * (f["nivel"] - base) + ("└─ " if f["nivel"] > base else "") + f["nombre"]
        tabla(filas, {"persona": "Persona", "cargo": "Cargo", "area": "Área", "nivel": "Nivel",
                      "personas_a_cargo": "Personas a cargo", "ruta_mando": "Ruta de mando"}, height=560)

with b2:
    quien = st.selectbox("Empleado con el incidente", staff, index=len(staff) - 1 if staff else None, key="b2",
                         format_func=lambda s: f"{s['nombre']} · {s['cargo']}")
    if quien:
        cadena = get(f"/reportes/escalamiento/{quien['id']}") or []
        for c in cadena:
            c["orden"] = "Persona" if c["paso"] == 0 else f"{c['paso']}° escalamiento"
        tabla(cadena, {"orden": "Orden", "nombre": "Nombre", "cargo": "Cargo", "area": "Área", "correo": "Correo"})
        if len(cadena) > 1:
            st.markdown(" → ".join(f"**{c['nombre']}**" for c in cadena))

with b3:
    filas = get("/reportes/ranking-clientes") or []
    if filas:
        df = pd.DataFrame(filas)
        fig = go.Figure()
        fig.add_bar(x=df["cliente"], y=df["total_facturado"], name="Total facturado",
                    marker_color=["#2563eb" if s.startswith("A") else "#94a3b8" for s in df["segmento"]])
        fig.add_scatter(x=df["cliente"], y=df["pct_acumulado"], name="% acumulado", yaxis="y2",
                        mode="lines+markers", line=dict(color="#dc2626"))
        fig.add_hline(y=80, line_dash="dot", yref="y2", line_color="#dc2626")
        fig.update_layout(yaxis=dict(title="COP"), yaxis2=dict(title="% acumulado", overlaying="y", side="right",
                                                               range=[0, 105]),
                          legend=dict(orientation="h"), height=430, margin=dict(t=30))
        st.plotly_chart(fig, width="stretch")
        for f in filas:
            f["total"] = pesos(f["total_facturado"])
        tabla(filas, {"posicion": "#", "cliente": "Cliente", "tipo": "Tipo", "num_eventos": "Eventos",
                      "total": "Total facturado", "pct_participacion": "% participación",
                      "pct_acumulado": "% acumulado", "segmento": "Segmento"})

with b4:
    salones = get("/salones/") or []
    salon = st.selectbox("Salón", [None] + salones, key="b4",
                         format_func=lambda s: "Todos los salones" if s is None else s["nombre"])
    filas = get("/reportes/ocupacion-salones", {"salon_id": salon["id"] if salon else None}) or []
    if filas:
        df = pd.DataFrame(filas)
        fig = px.bar(df, x="evento", y="horas_acumuladas", color="salon",
                     labels={"evento": "Evento (orden cronológico)", "horas_acumuladas": "Horas reservadas acumuladas"})
        fig.update_layout(height=380, margin=dict(t=20))
        st.plotly_chart(fig, width="stretch")
        for f in filas:
            f["inicio"] = f["inicio"][:16].replace("T", " ")
            f["fin"] = f["fin"][:16].replace("T", " ")
        tabla(filas, {"salon": "Salón", "numero_en_salon": "N°", "evento": "Evento", "estado": "Estado",
                      "inicio": "Inicio", "fin": "Fin", "horas_evento": "Horas", "evento_anterior": "Evento anterior",
                      "dias_libres": "Días libres", "horas_acumuladas": "Horas acumuladas"})
