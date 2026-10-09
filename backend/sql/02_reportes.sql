
DROP FUNCTION IF EXISTS fn_organigrama(INTEGER);
DROP FUNCTION IF EXISTS fn_escalamiento(INTEGER);
DROP FUNCTION IF EXISTS fn_ranking_clientes();
DROP FUNCTION IF EXISTS fn_ocupacion_salones(INTEGER);

-- B1. Organigrama (CTE recursiva)
CREATE FUNCTION fn_organigrama(p_staff_id INTEGER DEFAULT NULL)
RETURNS TABLE (staff_id INTEGER, nombre VARCHAR, cargo VARCHAR, area VARCHAR, jefe_id INTEGER,
               jefe VARCHAR, nivel INTEGER, ruta_mando TEXT, personas_a_cargo BIGINT)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE arbol AS (
        SELECT s.id, s.nombre, s.cargo, s.area, s.jefe_id,
               1 AS nivel,
               s.nombre::TEXT AS ruta,
               ARRAY[s.id] AS ruta_ids
        FROM staff s
        WHERE s.jefe_id IS NULL

        UNION ALL

        SELECT h.id, h.nombre, h.cargo, h.area, h.jefe_id,
               a.nivel + 1,
               a.ruta || ' > ' || h.nombre,
               a.ruta_ids || h.id
        FROM staff h
        JOIN arbol a ON h.jefe_id = a.id
        WHERE NOT h.id = ANY(a.ruta_ids) 
    )
    SELECT a.id, a.nombre, a.cargo, a.area, a.jefe_id, j.nombre, a.nivel, a.ruta,
           (SELECT COUNT(*) FROM arbol x
             WHERE a.id = ANY(x.ruta_ids) AND x.id <> a.id) AS personas_a_cargo
    FROM arbol a
    LEFT JOIN staff j ON j.id = a.jefe_id
    WHERE p_staff_id IS NULL OR p_staff_id = ANY(a.ruta_ids)
    ORDER BY a.ruta_ids;
$$;

-- B2. Cadena de escalamiento (CTE recursiva)
CREATE FUNCTION fn_escalamiento(p_staff_id INTEGER)
RETURNS TABLE (paso INTEGER, staff_id INTEGER, nombre VARCHAR, cargo VARCHAR, area VARCHAR, correo VARCHAR)
LANGUAGE sql STABLE AS $$
    WITH RECURSIVE cadena AS (
        SELECT 0 AS paso, s.id, s.nombre, s.cargo, s.area, s.correo, s.jefe_id, ARRAY[s.id] AS visitados
        FROM staff s
        WHERE s.id = p_staff_id

        UNION ALL

        SELECT c.paso + 1, j.id, j.nombre, j.cargo, j.area, j.correo, j.jefe_id, c.visitados || j.id
        FROM cadena c
        JOIN staff j ON j.id = c.jefe_id
        WHERE NOT j.id = ANY(c.visitados)        -- protección contra ciclos
    )
    SELECT paso, id, nombre, cargo, area, correo FROM cadena ORDER BY paso;
$$;

-- B3. Ranking de clientes y Pareto (funciones de ventana)
CREATE FUNCTION fn_ranking_clientes()
RETURNS TABLE (posicion BIGINT, cliente_id INTEGER, cliente VARCHAR, tipo VARCHAR, num_eventos BIGINT,
               total_facturado NUMERIC, pct_participacion NUMERIC, pct_acumulado NUMERIC, segmento TEXT)
LANGUAGE sql STABLE AS $$
    WITH por_cliente AS (
        SELECT c.id, c.nombre, c.tipo,
               COUNT(e.id)                       AS num_eventos,
               COALESCE(SUM(e.valor_total), 0)   AS total
        FROM clientes c
        LEFT JOIN eventos e ON e.cliente_id = c.id AND e.estado <> 'Cancelado'
        GROUP BY c.id, c.nombre, c.tipo
    ),
    calculado AS (
        SELECT p.*,
               RANK() OVER (ORDER BY p.total DESC)                         AS posicion,
               SUM(p.total) OVER ()                                         AS gran_total,
               SUM(p.total) OVER (ORDER BY p.total DESC, p.id
                                  ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS acumulado
        FROM por_cliente p
    )
    SELECT posicion, id, nombre, tipo, num_eventos, total,
           ROUND(100 * total / NULLIF(gran_total, 0), 2)                    AS pct_participacion,
           ROUND(100 * acumulado / NULLIF(gran_total, 0), 2)                AS pct_acumulado,
           CASE WHEN (acumulado - total) < 0.8 * gran_total THEN 'A (80%)' ELSE 'B (20%)' END AS segmento
    FROM calculado
    ORDER BY total DESC, id;
$$;

-- B4. Ocupación de salones y tiempos muertos (funciones de ventana)
CREATE FUNCTION fn_ocupacion_salones(p_salon_id INTEGER DEFAULT NULL)
RETURNS TABLE (salon_id INTEGER, salon VARCHAR, numero_en_salon BIGINT, evento_id INTEGER, evento VARCHAR,
               estado VARCHAR, inicio TIMESTAMP, fin TIMESTAMP, horas_evento NUMERIC,
               evento_anterior VARCHAR, fin_anterior TIMESTAMP, dias_libres NUMERIC, horas_acumuladas NUMERIC)
LANGUAGE sql STABLE AS $$
    SELECT s.id, s.nombre,
           ROW_NUMBER() OVER w                                         AS numero_en_salon,
           e.id, e.nombre, e.estado, e.inicio, e.fin,
           ROUND(fn_horas(e.inicio, e.fin), 2)                         AS horas_evento,
           LAG(e.nombre) OVER w                                        AS evento_anterior,
           LAG(e.fin)    OVER w                                        AS fin_anterior,
           ROUND(EXTRACT(EPOCH FROM (e.inicio - LAG(e.fin) OVER w)) / 86400.0, 2) AS dias_libres,
           ROUND(SUM(fn_horas(e.inicio, e.fin)) OVER (w ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW), 2)
                                                                       AS horas_acumuladas
    FROM eventos e
    JOIN salones s ON s.id = e.salon_id
    WHERE e.estado <> 'Cancelado'
      AND (p_salon_id IS NULL OR s.id = p_salon_id)
    WINDOW w AS (PARTITION BY s.id ORDER BY e.inicio)
    ORDER BY s.id, e.inicio;
$$;

-- Vista de apoyo: resumen de asistencia por evento 
CREATE OR REPLACE VIEW vw_asistencia_eventos AS
SELECT e.id AS evento_id,
       e.aforo_esperado,
       COUNT(i.id)              AS inscritos,
       COUNT(i.fecha_checkin)   AS llegaron,
       e.aforo_esperado - COUNT(i.id) AS cupos_libres,
       e.tasa_asistencia
FROM eventos e
LEFT JOIN inscripciones i ON i.evento_id = e.id
GROUP BY e.id, e.aforo_esperado, e.tasa_asistencia;
