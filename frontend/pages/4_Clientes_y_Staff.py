from datetime import date

import streamlit as st

from api_cliente import barra_lateral, enviar, get, pesos, tabla

st.set_page_config(page_title="Clientes y staff · NexoEventos", page_icon="👥", layout="wide")
barra_lateral()
st.title("👥 Clientes y staff")

AREAS = ["Dirección", "Operaciones", "Comercial", "Logística", "Alimentos y Bebidas", "Audiovisuales"]
t_cli, t_staff = st.tabs(["🏢 Clientes", "🧑‍💼 Staff"])

with t_cli:
    with st.expander("➕ Registrar cliente"):
        with st.form("form_cliente", clear_on_submit=True):
            c1, c2 = st.columns(2)
            tipo = c1.selectbox("Tipo", ["Empresa", "Persona"], help="Empresa = NIT · Persona = cédula")
            doc = c2.text_input("NIT o cédula")
            nom = st.text_input("Nombre o razón social")
            c1, c2 = st.columns(2)
            cor = c1.text_input("Correo")
            tel = c2.text_input("Teléfono")
            if st.form_submit_button("Registrar", type="primary"):
                enviar("POST", "/clientes/", {"tipo": tipo, "documento": doc, "nombre": nom,
                                               "correo": cor, "telefono": tel}, exito="Cliente registrado.")
    q = st.text_input("Buscar cliente (nombre o documento)")
    clientes = get("/clientes/", {"q": q}) or []
    tabla(clientes, {"tipo": "Tipo", "documento": "Documento", "nombre": "Nombre", "correo": "Correo",
                     "telefono": "Teléfono", "fecha_registro": "Registro"})
    if clientes:
        cli = st.selectbox("Ver eventos de", clientes, format_func=lambda c: c["nombre"])
        evs = get(f"/clientes/{cli['id']}/eventos") or []
        for e in evs:
            e["inicio"] = e["inicio"][:16].replace("T", " ")
            e["valor"] = pesos(e["valor_total"])
        tabla(evs, {"id": "Id", "nombre": "Evento", "estado": "Estado", "inicio": "Inicio", "valor": "Valor total"})

with t_staff:
    staff = get("/staff/") or []
    with st.expander("➕ Registrar empleado"):
        with st.form("form_staff", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nombre")
            cargo = c2.text_input("Cargo")
            c1, c2 = st.columns(2)
            area = c1.selectbox("Área", AREAS)
            cor = c2.text_input("Correo")
            c1, c2 = st.columns(2)
            ingreso = c1.date_input("Fecha de ingreso", date.today())
            jefe = c2.selectbox("Jefe inmediato", staff, format_func=lambda s: f"{s['nombre']} · {s['cargo']}")
            if st.form_submit_button("Registrar", type="primary"):
                enviar("POST", "/staff/", {"nombre": nom, "cargo": cargo, "area": area, "correo": cor,
                                            "fecha_ingreso": ingreso.isoformat(),
                                            "jefe_id": jefe["id"] if jefe else None},
                       exito="Empleado registrado.")
                staff = get("/staff/") or []
    nombres = {s["id"]: s["nombre"] for s in staff}
    for s in staff:
        s["jefe"] = nombres.get(s["jefe_id"], "— (dirección general)")
    tabla(staff, {"id": "Id", "nombre": "Nombre", "cargo": "Cargo", "area": "Área", "jefe": "Jefe inmediato",
                  "correo": "Correo"})
