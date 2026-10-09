from datetime import date, datetime, time, timedelta

import streamlit as st

from api_cliente import barra_lateral, enviar, etiqueta_evento, get, pesos, tabla, unir

st.set_page_config(page_title="Eventos · NexoEventos", page_icon="📅", layout="wide")
barra_lateral()
st.title("📅 Eventos")

TIPOS = ["Congreso", "Conferencia", "Feria", "Seminario", "Corporativo", "Social"]


def selector_horario(prefijo: str, ini: datetime = None, fin: datetime = None):
    """Fecha y hora de inicio y fin; el fin puede caer al día siguiente."""
    ini = ini or datetime.combine(date.today() + timedelta(days=7), time(8, 0))
    fin = fin or ini + timedelta(hours=4)
    c1, c2, c3, c4 = st.columns(4)
    f_ini = c1.date_input("Fecha inicio", ini.date(), key=f"{prefijo}_fi")
    h_ini = c2.time_input("Hora inicio", ini.time(), step=1800, key=f"{prefijo}_hi")
    f_fin = c3.date_input("Fecha fin", fin.date(), key=f"{prefijo}_ff", help="Puede ser el día siguiente")
    h_fin = c4.time_input("Hora fin", fin.time(), step=1800, key=f"{prefijo}_hf")
    return unir(f_ini, h_ini), unir(f_fin, h_fin)


tab_lista, tab_crear, tab_gestion = st.tabs(["📋 Listado", "➕ Crear evento", "⚙️ Gestionar evento"])

# LISTADO
with tab_lista:
    c1, c2 = st.columns([1, 2])
    estado = c1.selectbox("Estado", ["(todos)", "Cotizado", "Confirmado", "Finalizado", "Cancelado"])
    q = c2.text_input("Buscar por nombre")
    eventos = get("/eventos/", {"estado": None if estado == "(todos)" else estado, "q": q}) or []
    for e in eventos:
        e["inicio"] = e["inicio"][:16].replace("T", " ")
        e["fin"] = e["fin"][:16].replace("T", " ")
        e["valor"] = pesos(e["valor_total"])
        e["tasa"] = "—" if e["tasa_asistencia"] is None else f"{e['tasa_asistencia']:.2f} %"
    tabla(eventos, {"id": "Id", "nombre": "Evento", "tipo": "Tipo", "estado": "Estado", "inicio": "Inicio",
                    "fin": "Fin", "aforo_esperado": "Aforo", "valor": "Valor total", "tasa": "Tasa asistencia"})

# CREAR
with tab_crear:
    st.markdown("**1. Defina horario y aforo** · **2. Elija entre los salones disponibles** · **3. Cree el evento**")
    clientes = get("/clientes/") or []
    staff = get("/staff/") or []

    c1, c2 = st.columns(2)
    nombre = c1.text_input("Nombre del evento")
    tipo = c2.selectbox("Tipo", TIPOS)
    c1, c2 = st.columns(2)
    cliente = c1.selectbox("Cliente", clientes, format_func=lambda c: f"{c['nombre']} ({c['documento']})")
    coordinador = c2.selectbox("Coordinador (obligatorio para confirmar)", [None] + staff,
                               format_func=lambda s: "— sin asignar —" if s is None else f"{s['nombre']} · {s['cargo']}")
    inicio, fin = selector_horario("crear")
    aforo = st.number_input("Aforo esperado (personas)", min_value=1, value=50, step=5)

    if st.button("🔎 Buscar salones disponibles", type="secondary"):
        disponibles = get("/salones/disponibles", {"inicio": inicio, "fin": fin, "aforo": aforo})
        st.session_state["disponibles_crear"] = disponibles
        st.session_state["consulta_crear"] = (inicio, fin, aforo)

    disponibles = st.session_state.get("disponibles_crear")
    if disponibles is not None:
        if st.session_state.get("consulta_crear") != (inicio, fin, aforo):
            st.warning("Cambió el horario o el aforo: vuelva a buscar salones disponibles.")
        elif not disponibles:
            st.warning("No hay salones disponibles para ese horario y aforo.")
        else:
            salon = st.radio("Salones disponibles (del más ajustado al más grande)", disponibles,
                             format_func=lambda s: f"{s['nombre']} · {s['tamano']} · {s['capacidad']} personas · "
                                                   f"costo del salón {pesos(s['costo_estimado'])}")
            if st.button("✅ Crear evento", type="primary"):
                ok, nuevo = enviar("POST", "/eventos/", {
                    "cliente_id": cliente["id"] if cliente else None, "salon_id": salon["salon_id"],
                    "coordinador_id": coordinador["id"] if coordinador else None, "nombre": nombre,
                    "tipo": tipo, "inicio": inicio, "fin": fin, "aforo_esperado": aforo},
                    exito="Evento creado como Cotizado.")
                if ok:
                    st.session_state.pop("disponibles_crear", None)
                    st.write(f"Evento **#{nuevo['id']}** · valor inicial (salón): **{pesos(nuevo['valor_total'])}**. "
                             "Agregue servicios en la pestaña *Gestionar evento*.")

# GESTIONAR
with tab_gestion:
    todos = get("/eventos/") or []
    if not todos:
        st.stop()
    elegido = st.selectbox("Evento", todos, format_func=etiqueta_evento, key="evento_gestion")
    eid = elegido["id"]

    t_serv, t_cot, t_estado, t_repro, t_aud = st.tabs(
        ["🧾 Servicios", "💰 Cotización", "🔁 Estado", "🗓️ Reprogramar", "🕵️ Auditoría"])


    with t_serv:
        catalogo = get("/servicios/") or []
        st.markdown("**Agregar servicio** · si deja la cantidad en 0, la base usa el aforo (por persona) "
                    "o las horas del evento (por hora). El precio queda congelado.")
        c1, c2, c3 = st.columns([3, 1, 1])
        serv = c1.selectbox("Servicio", catalogo,
                            format_func=lambda s: f"{s['nombre']} · {s['unidad_cobro']} · {pesos(s['precio_unitario'])}")
        cant = c2.number_input("Cantidad", min_value=0, value=0, key="cant_add")
        if c3.button("Agregar", width="stretch"):
            enviar("POST", f"/eventos/{eid}/servicios",
                   {"servicio_id": serv["id"], "cantidad": cant or None}, exito="Servicio agregado.")

        contratados = get(f"/eventos/{eid}/servicios") or []
        if contratados:
            st.markdown("**Modificar o quitar un servicio contratado**")
            c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
            linea = c1.selectbox("Servicio contratado", contratados, format_func=lambda l: l["servicio"])
            nueva = c2.number_input("Nueva cantidad (0 = automática)", min_value=0, value=0, key="cant_put")
            if c3.button("Modificar", width="stretch"):
                enviar("PUT", f"/eventos/{eid}/servicios/{linea['servicio_id']}",
                       {"cantidad": nueva or None}, exito="Cantidad actualizada.")
            if c4.button("Quitar", width="stretch"):
                enviar("DELETE", f"/eventos/{eid}/servicios/{linea['servicio_id']}", exito="Servicio retirado.")

    with t_estado:
        st.markdown("Flujo: **Cotizado → Confirmado → Finalizado**; desde Cotizado o Confirmado se puede **Cancelar**. "
                    "Finalizado y Cancelado son definitivos.")
        c1, c2, c3 = st.columns(3)
        if c1.button("✔️ Confirmar", width="stretch"):
            enviar("PATCH", f"/eventos/{eid}/estado", {"estado": "Confirmado"}, exito="Evento confirmado.")
        if c2.button("🏁 Finalizar", width="stretch"):
            ok, r = enviar("PATCH", f"/eventos/{eid}/estado", {"estado": "Finalizado"}, exito="Evento finalizado.")
            if ok:
                st.info("Tasa de asistencia calculada por la base: " +
                        ("sin inscritos" if r["tasa_asistencia"] is None else f"{r['tasa_asistencia']:.2f} %"))
        if c3.button("✖️ Cancelar evento", width="stretch"):
            enviar("PATCH", f"/eventos/{eid}/estado", {"estado": "Cancelado"}, exito="Evento cancelado; el salón queda libre.")

    with t_repro:
        actual = get(f"/eventos/{eid}")
        if actual:
            st.caption("Cambie solo lo necesario. Para cambiar de salón se ofrecen solo los disponibles en el nuevo horario.")
            ini, fn = selector_horario(f"repro{eid}", datetime.fromisoformat(actual["inicio"]),
                                       datetime.fromisoformat(actual["fin"]))
            c1, c2 = st.columns(2)
            nuevo_aforo = c1.number_input("Aforo", min_value=1, value=actual["aforo_esperado"], key=f"aforo{eid}")
            staff = get("/staff/") or []
            idx = next((i for i, s in enumerate(staff) if s["id"] == actual["coordinador_id"]), None)
            coord = c2.selectbox("Coordinador", staff, index=idx, placeholder="— sin asignar —",
                                 format_func=lambda s: f"{s['nombre']} · {s['cargo']}", key=f"coord{eid}")
            libres = get("/salones/disponibles", {"inicio": ini, "fin": fn, "aforo": nuevo_aforo,
                                                  "excluir_evento": eid}) if fn > ini else []
            opciones = list(libres or [])
            if actual["salon_id"] not in [s["salon_id"] for s in opciones]:
                # El salón actual siempre se ofrece; si ya no sirve, la base lo rechaza (A1) y se ve el motivo
                opciones.insert(0, {"salon_id": actual["salon_id"], "nombre": actual["salon"], "capacidad": None})
            pos = [s["salon_id"] for s in opciones].index(actual["salon_id"])
            salon = st.selectbox("Salón", opciones, index=pos, key=f"salon{eid}",
                                 format_func=lambda s: f"{s['nombre']} · actual (no figura como disponible)"
                                 if s["capacidad"] is None else f"{s['nombre']} · {s['capacidad']} personas")
            if st.button("💾 Guardar reprogramación", type="primary"):
                cambios = {}
                if ini != actual["inicio"][:16]:
                    cambios["inicio"] = ini
                if fn != actual["fin"][:16]:
                    cambios["fin"] = fn
                if nuevo_aforo != actual["aforo_esperado"]:
                    cambios["aforo_esperado"] = nuevo_aforo
                if salon and salon["salon_id"] != actual["salon_id"]:
                    cambios["salon_id"] = salon["salon_id"]
                if coord and coord["id"] != actual["coordinador_id"]:
                    cambios["coordinador_id"] = coord["id"]
                if cambios:
                    enviar("PATCH", f"/eventos/{eid}", cambios, exito="Evento reprogramado.")
                else:
                    st.info("No hay cambios para guardar.")

    # ---------- vistas (se leen después de las acciones)
    detalle = get(f"/eventos/{eid}")
    if detalle:
        with st.container(border=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("Estado", detalle["estado"])
            c2.metric("Valor total", pesos(detalle["valor_total"]))
            a = detalle["asistencia"]
            c3.metric("Inscritos / aforo", f"{a['inscritos']} / {a['aforo_esperado']}")
            c4.metric("Llegaron", a["llegaron"])
            c5.metric("Tasa de asistencia", "—" if a["tasa_asistencia"] is None else f"{a['tasa_asistencia']:.2f} %")
            st.caption(f"Cliente: {detalle['cliente']} · Salón: {detalle['salon']} · "
                       f"Coordinador: {detalle['coordinador'] or 'sin asignar'} · "
                       f"{detalle['inicio'][:16].replace('T', ' ')} → {detalle['fin'][:16].replace('T', ' ')}")

    with t_serv:
        st.markdown("**Servicios contratados**")
        lineas = get(f"/eventos/{eid}/servicios") or []
        for l in lineas:
            l["modo"] = "automática" if l["cantidad_automatica"] else "manual"
            l["precio"] = pesos(l["precio_unitario"])
            l["sub"] = pesos(l["subtotal"])
        tabla(lineas, {"servicio": "Servicio", "unidad_cobro": "Se cobra", "cantidad": "Cantidad", "modo": "Modo",
                       "precio": "Precio congelado", "sub": "Subtotal"})

    with t_cot:
        cot = get(f"/eventos/{eid}/cotizacion")
        if cot:
            for l in cot["lineas"]:
                l["precio"] = pesos(l["precio_unitario"])
                l["sub"] = pesos(l["subtotal"])
            tabla(cot["lineas"], {"concepto": "Concepto", "unidad": "Unidad", "cantidad": "Cantidad",
                                  "precio": "Precio unitario", "sub": "Subtotal"})
            st.markdown(f"### Total: {pesos(cot['total'])}")
            st.caption(f"Valor total guardado por la base (trigger A3): {pesos(cot['valor_total_en_base'])}")

    with t_aud:
        aud = get(f"/eventos/{eid}/auditoria") or []
        for x in aud:
            x["fecha"] = x["fecha"][:19].replace("T", " ")
        tabla(aud, {"fecha": "Fecha", "campo": "Campo", "valor_anterior": "Valor anterior",
                    "valor_nuevo": "Valor nuevo", "usuario": "Usuario de la app"})
