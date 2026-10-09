# NexoEventos

Ingeniería de Datos · Parcial 2

**Entregable 1 – Backend** · Integrantes: Juan Felipe Cortés, Sara Isabella Patiño, Manuela Vergara

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
## Estructura del proyecto

| Carpeta | Contenido |
|---|---|
| `backend/` | Código de la API. `main.py` crea las tablas y aplica los scripts SQL al iniciar; `app/` contiene las entidades (`models.py`), los DTO (`schemas.py`), la traducción de errores (`errores.py`) y un router por recurso. Incluye `cargar_datos.py` y `reiniciar_base.py` para la carga de datos de prueba. |
| `backend/sql/` | Lógica que vive en PostgreSQL: `01_logica_eventos.sql` (triggers y funciones A1–A5), `02_reportes.sql` (B1–B4), `03_catalogo.sql` (salones y servicios oficiales) y `04_datos_prueba.sql`. |
| `frontend/` | Interfaz en Streamlit: tablero, eventos, asistentes y check-in, disponibilidad de salones, clientes y staff, y reportes con gráficos. Nunca se conecta a la base: todo pasa por la API. |
| `postman/` | `NexoEventos.postman_collection.json`, con las peticiones de cada regla y la verificación del código HTTP esperado. |
| `documentacion/` | `Diagrama_relacional.pdf`, `Diccionario_de_datos.pdf`, `Lista_de_endpoints.pdf` y las capturas de evidencias de A1–A5 y B1–B4. |
