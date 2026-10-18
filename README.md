# NexoEventos · Centro de Convenciones Nexo

Ingeniería de Datos · Proyecto Integrador (Parcial 2) · Universidad del Rosario, Escuela de Ciencias e Ingeniería

**Entrega final (backend + frontend)** · Integrantes: [Nombre] Cortéz, [Nombre] Patiño, [Nombre] Vergara

## Descripción

El Centro de Convenciones Nexo alquila seis salones y un catálogo de servicios (bebidas, refrigerios y audiovisuales) para congresos, conferencias, ferias, seminarios y eventos corporativos y sociales. Hoy lo gestiona en hojas de cálculo, lo que produce dobles reservas, cotizaciones manuales y ninguna medición de la asistencia real.

**NexoEventos** resuelve ese problema con reglas que la propia base de datos hace cumplir, aunque alguien inserte datos desde pgAdmin sin pasar por la API:

1. **Sin dobles reservas:** ningún salón tiene dos eventos cruzados, con 1 hora de montaje entre ellos, y el aforo nunca supera la capacidad.
2. **Liquidación automática:** el valor de cada evento (alquiler del salón + servicios con precio congelado) siempre está actualizado sin que la aplicación lo calcule.
3. **Asistencia real y trazabilidad:** cada evento finalizado guarda su tasa de asistencia (llegaron ÷ inscritos) y cada cambio de estado, salón u horario queda auditado con el usuario de la aplicación.

## Arquitectura

Tres capas. El frontend **nunca** se conecta a la base: todo pasa por la API.

```
Streamlit (frontend/)  ──HTTP──▶  FastAPI (backend/)  ──SQLAlchemy──▶  PostgreSQL
                                                         triggers A1–A4, función A5,
                                                         reportes B1–B4 (backend/sql/)
```

| Componente | Tecnología | Rol |
|---|---|---|
| `backend/` | FastAPI + SQLAlchemy + Pydantic | API REST: entidades (`app/models.py`), DTO (`app/schemas.py`), traducción de errores (`app/errores.py`) y un router por recurso (`app/routers/`). |
| `backend/sql/` | PostgreSQL (PL/pgSQL) | Triggers, funciones y vistas que la API aplica al iniciar, después de `Base.metadata.create_all(...)`; catálogo oficial y datos de prueba. |
| `frontend/` | Streamlit | Seis módulos: tablero, eventos, asistentes y check-in, disponibilidad, clientes y staff, y reportes con gráficos. Consume solo la API y muestra la regla violada cuando la base rechaza una operación. |
| `postman/` | Postman | Colección con un caso permitido y uno bloqueado por regla, con tests del código HTTP esperado. |
| `documentacion/` | PDF | Diagrama relacional, diccionario de datos, lista de endpoints, manual de rutas y manual de usuario del frontend. |

## Estructura del proyecto

```
Cortez_Patino_Vergara/
├── backend/          API REST en FastAPI: conexión a la base, entidades, DTO, manejo de errores y routers
│   └── sql/          Scripts de PostgreSQL: triggers y funciones (A1–A5), reportes (B1–B4), catálogo y datos de prueba
├── frontend/         Aplicación en Streamlit que consume la API
├── postman/          Colección de pruebas con un caso permitido y uno bloqueado por cada regla
├── documentacion/    Diagrama, diccionario, endpoints, manual de rutas y manual de usuario
└── README.md         Descripción del sistema y pasos para levantarlo desde una base vacía
```

| Carpeta | Contenido |
|---|---|
| `backend/` | Código de la API. `main.py` crea las tablas y aplica los scripts SQL al iniciar; `app/` contiene las entidades (`models.py`), los DTO (`schemas.py`), la traducción de errores (`errores.py`) y un router por recurso. Incluye `cargar_datos.py` y `reiniciar_base.py` para los datos de prueba. |
| `backend/sql/` | Lógica que vive en PostgreSQL: `01_logica_eventos.sql` (triggers y funciones A1–A5), `02_reportes.sql` (B1–B4), `03_catalogo.sql` (salones y servicios oficiales) y `04_datos_prueba.sql`. |
| `frontend/` | `Inicio.py` (tablero), `api_cliente.py` (llamadas a la API y manejo de errores) y `pages/` con los módulos de eventos, asistentes y check-in, disponibilidad, clientes y staff, y reportes. |
| `postman/` | `NexoEventos.postman_collection.json`, con las peticiones de cada regla y la verificación del código HTTP esperado. |
| `documentacion/` | `Diagrama_relacional.pdf`, `Diccionario_de_datos.pdf`, `Lista_de_endpoints.pdf`, `Manual_de_rutas.pdf` y `Manual_de_usuario.pdf`. |

## Modelo de datos

Nueve tablas en tercera forma normal, generadas por las entidades de SQLAlchemy. El detalle de cada campo está en `documentacion/Diccionario_de_datos.pdf` y el modelo completo en `documentacion/Diagrama_relacional.pdf`.

| Tabla | Entidad | Descripción |
|---|---|---|
| `clientes` | `ClienteEntity` | Empresa (NIT) o persona natural (cédula). Documento único. |
| `salones` | `SalonEntity` | Los 6 salones, con tamaño, capacidad, precio por hora y estado activo. |
| `servicios` | `ServicioEntity` | Catálogo cobrado por persona, por hora o por unidad. |
| `staff` | `StaffEntity` | Empleados con auto-referencia `jefe_id`; la dirección general no tiene jefe. |
| `eventos` | `EventoEntity` | Evento de un cliente en un salón; guarda valor total y tasa de asistencia calculados por la base. |
| `evento_servicios` | `EventoServicioEntity` | N:M eventos ↔ servicios con cantidad y precio congelado. |
| `asistentes` | `AsistenteEntity` | Visitantes, con documento único. |
| `inscripciones` | `InscripcionEntity` | N:M asistentes ↔ eventos; `fecha_checkin` es la asistencia real. |
| `auditoria_eventos` | `AuditoriaEventoEntity` | Cambios de estado, salón u horario con valor anterior, nuevo, fecha y usuario de la aplicación. |

## Módulo A · Triggers y funciones (`backend/sql/01_logica_eventos.sql`)

Todas las reglas lanzan `RAISE EXCEPTION 'REGLA: mensaje'`. La API toma lo que va antes de los dos puntos como nombre de la regla y responde **409** con el mensaje; el `HINT` llega como `sugerencia`. Como viven en la base, se cumplen igual si alguien inserta desde pgAdmin o psql.

PostgreSQL dispara los triggers de una tabla en orden alfabético; por eso tienen números en el nombre.

| Trigger | Tabla y momento | Regla |
|---|---|---|
| trg_eventos_10_estado | eventos, BEFORE INSERT/UPDATE | A4: ciclo de vida y tasa de asistencia |
| trg_eventos_20_disponibilidad | eventos, BEFORE INSERT/UPDATE | A1: salón activo, capacidad y cruces |
| trg_eventos_30_liquidacion | eventos, BEFORE INSERT/UPDATE | A3: recalcula valor_total y cantidades automáticas |
| trg_eventos_90_auditoria | eventos, AFTER INSERT/UPDATE | A4: auditoría |
| trg_es_10_validar | evento_servicios, BEFORE INSERT/UPDATE/DELETE | A3: congela precio, cantidad por defecto, bloquea si el evento está cerrado |
| trg_es_90_total | evento_servicios, AFTER INSERT/UPDATE/DELETE | A3: actualiza el total del evento |
| trg_inscripciones_10_cupo_checkin | inscripciones, BEFORE INSERT/UPDATE | A2: cupo, estado, ventana de check-in, una sola llegada |
| trg_staff_10_jerarquia | staff, BEFORE INSERT/UPDATE de jefe_id | Impide ciclos en la jerarquía |

**A1 · Disponibilidad.** Dos eventos del mismo salón se cruzan, contando la hora de montaje, si `otro.inicio < nuevo.fin + 1 h` y `otro.fin + 1 h > nuevo.inicio`. Se ignoran los cancelados y el propio evento (para poder reprogramarlo). La regla actúa al crear, al cambiar salón, horario o aforo, y al cambiar de estado (reactivación). También impide bajar el aforo por debajo de los inscritos.

**A2 · Cupos y check-in.** Al inscribir, bloquea el evento con `SELECT … FOR UPDATE` para que dos inscripciones simultáneas no se salten el cupo. El check-in compara la hora de llegada indicada (no la hora actual), lo que permite registrar asistencias históricas en los datos de prueba.

**A3 · Liquidación.** `valor_total = horas exactas × precio_hora + Σ subtotales`. Si no llega cantidad, se usa el aforo (por persona), las horas redondeadas hacia arriba (por hora) o 1 (por unidad), y se marca `cantidad_automatica`. Al reprogramar, esas cantidades automáticas se ajustan; las manuales se respetan. La bandera de sesión `nexo.recalculando` evita que el trigger de servicios vuelva a actualizar el evento mientras el evento se recalcula a sí mismo.

**A4 · Cierre y auditoría.** Flujo permitido: Cotizado → Confirmado → Finalizado, y Cotizado/Confirmado → Cancelado. Confirmar exige coordinador. Finalizar exige que la hora de fin ya haya pasado y calcula `ROUND(llegaron × 100 / inscritos, 2)` (NULL sin inscritos). El usuario se obtiene así: la API ejecuta `set_config('nexo.usuario', X-Usuario, true)` al iniciar cada transacción (`app/database.py`) y el trigger lo lee con `current_setting('nexo.usuario', true)`.

**A5 · `fn_salones_disponibles(inicio, fin, aforo, excluir_evento)`.** Reutiliza la misma función de cruce de A1 (`fn_evento_en_conflicto`), así que ambas reglas nunca se contradicen. Ordena por capacidad (el más ajustado primero) y devuelve el costo del salón para ese horario.

## Módulo B · Reportes (`backend/sql/02_reportes.sql`)

| Función | Técnica | Qué responde |
|---|---|---|
| fn_organigrama(staff_id) | CTE recursiva desde la dirección; arreglo `ruta_ids` para la ruta y para cortar ciclos | Personas a cargo directas e indirectas, nivel, ruta de mando |
| fn_escalamiento(staff_id) | CTE recursiva hacia arriba, con arreglo de visitados | A quién escalar un incidente |
| fn_ranking_clientes() | `RANK()`, `SUM() OVER ()` (gran total), `SUM() OVER (ORDER BY …)` (acumulado) | Ranking, participación, acumulado y segmento Pareto |
| fn_ocupacion_salones(salon_id) | `ROW_NUMBER`, `LAG` con `PARTITION BY salón ORDER BY inicio`, suma acumulada | Número del evento en el salón, evento anterior, días libres, horas acumuladas |

Segmento Pareto: un cliente está en el segmento **A (80 %)** si el acumulado **antes** de él no llegaba al 80 %; así se incluye al cliente que cruza la línea.


## Endpoints

Todas las rutas aceptan el encabezado `X-Usuario`, que la API entrega a la base para la auditoría. Códigos: **201** al crear, **204** al borrar, **404** si no existe, **409** cuando un trigger rechaza la operación (con el mensaje de la regla), **422** cuando los datos son inválidos. Cada ruta, con sus parámetros, validaciones, errores posibles y un ejemplo real, está en `documentacion/Manual_de_rutas.pdf`; también se puede probar en Swagger (`/docs`).

| Recurso | Rutas principales |
|---|---|
| Clientes | `GET, POST /clientes/` · `GET /clientes/{id}/eventos` |
| Staff | `GET, POST /staff/` |
| Catálogo | `GET /salones/` · `GET /salones/disponibles` (A5) · `GET /servicios/` |
| Eventos | `GET, POST /eventos/` · `GET, PATCH /eventos/{id}` · `PATCH /eventos/{id}/estado` |
| Servicios del evento | `GET, POST /eventos/{id}/servicios` · `PUT, DELETE /eventos/{id}/servicios/{servicio_id}` · `GET /eventos/{id}/cotizacion` |
| Auditoría | `GET /eventos/{id}/auditoria` |
| Asistentes | `GET, POST /asistentes/` · `GET, POST /eventos/{id}/inscripciones` · `POST /eventos/{id}/checkin` |
| Reportes | `GET /reportes/organigrama` · `/reportes/escalamiento/{id}` · `/reportes/ranking-clientes` · `/reportes/ocupacion-salones` · `/reportes/tablero` |

## Cómo levantar el sistema desde una base vacía

Requisitos: PostgreSQL 14 o superior (con pgAdmin), Python 3.10 o superior y Postman.

**1. Crear la base.** En pgAdmin: clic derecho en **Databases → Create → Database…**, nombre `nexoeventos`. No cree tablas: las crea la API.

**2. Backend (terminal 1).**

```bash
cd backend
python -m venv venv
venv\Scripts\activate              # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env             # macOS/Linux: cp .env.example .env
```

Edite `backend/.env` con la clave y el puerto de su PostgreSQL:

```
DATABASE_URL=postgresql://postgres:SU_CLAVE@localhost:5432/nexoeventos
```

```bash
uvicorn main:app --reload
```

Al iniciar, la API crea las tablas y aplica `sql/01`, `sql/02` y `sql/03` (son idempotentes). Swagger queda en http://127.0.0.1:8000/docs.

**3. Datos de prueba (terminal 2, en `backend` con el venv activo).**

```bash
python cargar_datos.py
```

Respuesta esperada: `Carga terminada: 8 clientes, 17 staff, 14 eventos, 60 asistentes, 193 inscripciones.` Para volver a dejar la base como recién cargada en cualquier momento: `python reiniciar_base.py` (la API puede seguir encendida).

**4. Frontend (terminal 3).**

```bash
cd frontend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
streamlit run Inicio.py
```

Se abre en http://localhost:8501. Si la API corre en otra dirección, defina la variable de entorno `API_URL`. El uso de cada pantalla está en `documentacion/Manual_de_usuario.pdf`.

**5. Postman.** Importe `postman/NexoEventos.postman_collection.json` y ejecute las carpetas en orden sobre una base recién cargada; cada petición verifica el código HTTP esperado.

## Notas

- Las fechas de los datos de prueba corresponden al semestre 2026-2 (eventos pasados en agosto y septiembre, futuros entre octubre y diciembre). La zona horaria de la base se fija en `America/Bogota`.
- Si se modifica un evento directamente desde pgAdmin, la auditoría registra el usuario de la base marcado con "(bd)".
- La cadena de conexión vive solo en `backend/.env`, que no se sube al repositorio.
