
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'America/Bogota');
EXCEPTION WHEN insufficient_privilege THEN
    RAISE NOTICE 'Sin permisos para fijar la zona horaria de la base; se usa la del servidor.';
END $$;

-- Funciones de apoyo

-- Duración en horas para el alquiler del salón
CREATE OR REPLACE FUNCTION fn_horas(p_inicio TIMESTAMP, p_fin TIMESTAMP)
RETURNS NUMERIC LANGUAGE sql IMMUTABLE AS $$
    SELECT ROUND(EXTRACT(EPOCH FROM (p_fin - p_inicio)) / 3600.0, 4);
$$;

-- Duración en horas redondeada hacia arriba para servicios cobrados por hora
CREATE OR REPLACE FUNCTION fn_horas_cobro(p_inicio TIMESTAMP, p_fin TIMESTAMP)
RETURNS INTEGER LANGUAGE sql IMMUTABLE AS $$
    SELECT CEIL(EXTRACT(EPOCH FROM (p_fin - p_inicio)) / 3600.0)::INTEGER;
$$;

CREATE OR REPLACE FUNCTION fn_fmt(p_ts TIMESTAMP)
RETURNS TEXT LANGUAGE sql IMMUTABLE AS $$
    SELECT to_char(p_ts, 'YYYY-MM-DD HH24:MI');
$$;

-- Usuario de la aplicación enviado por la API.
CREATE OR REPLACE FUNCTION fn_usuario_app()
RETURNS TEXT LANGUAGE sql STABLE AS $$
    SELECT COALESCE(NULLIF(current_setting('nexo.usuario', true), ''), session_user || ' (bd)');
$$;

-- Primer evento NO cancelado del salón. (A1 y A5).
CREATE OR REPLACE FUNCTION fn_evento_en_conflicto(
    p_salon_id INTEGER, p_inicio TIMESTAMP, p_fin TIMESTAMP, p_excluir_evento INTEGER DEFAULT NULL)
RETURNS SETOF eventos LANGUAGE sql STABLE AS $$
    SELECT e.*
    FROM eventos e
    WHERE e.salon_id = p_salon_id
      AND e.estado <> 'Cancelado'
      AND e.id IS DISTINCT FROM p_excluir_evento
      AND e.inicio < p_fin + INTERVAL '1 hour'
      AND e.fin + INTERVAL '1 hour' > p_inicio
    ORDER BY e.inicio
    LIMIT 1;
$$;

-- Valor total = alquiler del salón (horas x precio/hora) + suma de servicios
CREATE OR REPLACE FUNCTION fn_valor_total(
    p_evento_id INTEGER, p_salon_id INTEGER, p_inicio TIMESTAMP, p_fin TIMESTAMP)
RETURNS NUMERIC LANGUAGE sql STABLE AS $$
    SELECT ROUND(
             (SELECT s.precio_hora * fn_horas(p_inicio, p_fin) FROM salones s WHERE s.id = p_salon_id)
           + COALESCE((SELECT SUM(es.subtotal) FROM evento_servicios es WHERE es.evento_id = p_evento_id), 0)
           , 2);
$$;


-- A4 (parte 1). Ciclo de vida del evento y tasa de asistencia
CREATE OR REPLACE FUNCTION fn_trg_eventos_estado()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_inscritos INTEGER;
    v_llegaron  INTEGER;
BEGIN
    IF TG_OP = 'INSERT' THEN
        NEW.estado := COALESCE(NEW.estado, 'Cotizado');
        IF NEW.estado <> 'Cotizado' THEN
            RAISE EXCEPTION 'ESTADO: Todo evento nace como Cotizado (se intentó crear como %).', NEW.estado;
        END IF;
        NEW.tasa_asistencia := NULL;
        RETURN NEW;
    END IF;

    IF OLD.estado IN ('Finalizado', 'Cancelado') THEN
        RAISE EXCEPTION 'ESTADO: El evento "%" está % y ese estado es definitivo; no admite cambios.',
            OLD.nombre, OLD.estado;
    END IF;

    IF NEW.estado <> OLD.estado THEN
        IF NOT ( (OLD.estado = 'Cotizado'   AND NEW.estado IN ('Confirmado', 'Cancelado'))
              OR (OLD.estado = 'Confirmado' AND NEW.estado IN ('Finalizado', 'Cancelado')) ) THEN
            RAISE EXCEPTION 'ESTADO: No se puede pasar el evento "%" de % a %.', OLD.nombre, OLD.estado, NEW.estado
                USING HINT = 'Flujo permitido: Cotizado -> Confirmado -> Finalizado; Cotizado/Confirmado -> Cancelado.';
        END IF;
    END IF;

    IF NEW.estado = 'Confirmado' AND NEW.coordinador_id IS NULL THEN
        RAISE EXCEPTION 'ESTADO: Para confirmar el evento "%" primero asigne un coordinador del staff.', NEW.nombre;
    END IF;

    IF NEW.estado = 'Finalizado' THEN
        IF NEW.fin > LOCALTIMESTAMP THEN
            RAISE EXCEPTION 'ESTADO: El evento "%" solo se puede finalizar después de su hora de fin (%).',
                NEW.nombre, fn_fmt(NEW.fin);
        END IF;
        SELECT COUNT(*), COUNT(fecha_checkin) INTO v_inscritos, v_llegaron
        FROM inscripciones WHERE evento_id = NEW.id;
        -- Tasa real = llegaron / inscritos; vacía si no hubo inscritos
        NEW.tasa_asistencia := CASE WHEN v_inscritos = 0 THEN NULL
                                    ELSE ROUND(v_llegaron * 100.0 / v_inscritos, 2) END;
    ELSE
        NEW.tasa_asistencia := OLD.tasa_asistencia;   -- nadie la edita a mano
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_eventos_10_estado ON eventos;
CREATE TRIGGER trg_eventos_10_estado
    BEFORE INSERT OR UPDATE ON eventos
    FOR EACH ROW EXECUTE FUNCTION fn_trg_eventos_estado();

-- A1. Disponibilidad y capacidad del salón
CREATE OR REPLACE FUNCTION fn_trg_eventos_disponibilidad()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_salon     salones%ROWTYPE;
    v_choque    eventos%ROWTYPE;
    v_inscritos INTEGER;
BEGIN
    IF NEW.estado IN ('Cancelado', 'Finalizado') THEN
        RETURN NEW;
    END IF;

    IF TG_OP = 'UPDATE'
       AND NEW.salon_id = OLD.salon_id AND NEW.inicio = OLD.inicio AND NEW.fin = OLD.fin
       AND NEW.aforo_esperado = OLD.aforo_esperado AND NEW.estado = OLD.estado THEN
        RETURN NEW;
    END IF;

    SELECT * INTO v_salon FROM salones WHERE id = NEW.salon_id;

    IF NOT v_salon.activo THEN
        RAISE EXCEPTION 'SALÓN INACTIVO: El salón "%" está deshabilitado temporalmente.', v_salon.nombre
            USING HINT = 'Consulte los salones disponibles para ese horario.';
    END IF;

    IF NEW.aforo_esperado > v_salon.capacidad THEN
        RAISE EXCEPTION 'CAPACIDAD: El aforo esperado (% personas) supera la capacidad del salón "%" (% personas).',
            NEW.aforo_esperado, v_salon.nombre, v_salon.capacidad
            USING HINT = 'Consulte los salones disponibles para ese horario.';
    END IF;

    SELECT * INTO v_choque FROM fn_evento_en_conflicto(NEW.salon_id, NEW.inicio, NEW.fin, NEW.id);
    IF FOUND THEN
        RAISE EXCEPTION 'DISPONIBILIDAD: El salón "%" está reservado para "%" (% a %). Se requiere 1 hora de montaje entre eventos.',
            v_salon.nombre, v_choque.nombre, fn_fmt(v_choque.inicio), fn_fmt(v_choque.fin)
            USING HINT = 'Consulte los salones disponibles para ese horario.';
    END IF;

    IF TG_OP = 'UPDATE' AND NEW.aforo_esperado < OLD.aforo_esperado THEN
        SELECT COUNT(*) INTO v_inscritos FROM inscripciones WHERE evento_id = NEW.id;
        IF NEW.aforo_esperado < v_inscritos THEN
            RAISE EXCEPTION 'CUPO: El evento "%" ya tiene % inscritos; el aforo no puede bajar a %.',
                NEW.nombre, v_inscritos, NEW.aforo_esperado;
        END IF;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_eventos_20_disponibilidad ON eventos;
CREATE TRIGGER trg_eventos_20_disponibilidad
    BEFORE INSERT OR UPDATE ON eventos
    FOR EACH ROW EXECUTE FUNCTION fn_trg_eventos_disponibilidad();

-- A3. Liquidación automática


-- A3.a Recalcula el valor total
CREATE OR REPLACE FUNCTION fn_trg_eventos_liquidacion()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND (NEW.inicio <> OLD.inicio OR NEW.fin <> OLD.fin
                             OR NEW.aforo_esperado <> OLD.aforo_esperado) THEN
        PERFORM set_config('nexo.recalculando', 'on', true);
        UPDATE evento_servicios es
           SET cantidad = CASE s.unidad_cobro
                              WHEN 'Por persona' THEN NEW.aforo_esperado
                              WHEN 'Por hora'    THEN fn_horas_cobro(NEW.inicio, NEW.fin)
                              ELSE es.cantidad END
          FROM servicios s
         WHERE s.id = es.servicio_id
           AND es.evento_id = NEW.id
           AND es.cantidad_automatica;
        PERFORM set_config('nexo.recalculando', 'off', true);
    END IF;

    NEW.valor_total := fn_valor_total(NEW.id, NEW.salon_id, NEW.inicio, NEW.fin);
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_eventos_30_liquidacion ON eventos;
CREATE TRIGGER trg_eventos_30_liquidacion
    BEFORE INSERT OR UPDATE ON eventos
    FOR EACH ROW EXECUTE FUNCTION fn_trg_eventos_liquidacion();


-- A3.b Congela el precio, calcula la cantidad por defecto y bloquea cambios en eventos finalizados
CREATE OR REPLACE FUNCTION fn_trg_es_validar()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_evento   eventos%ROWTYPE;
    v_servicio servicios%ROWTYPE;
BEGIN
    IF TG_OP = 'UPDATE' AND current_setting('nexo.recalculando', true) = 'on' THEN
        RETURN NEW;
    END IF;

    SELECT * INTO v_evento FROM eventos
     WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.evento_id ELSE NEW.evento_id END;

    IF v_evento.estado IN ('Finalizado', 'Cancelado') THEN
        RAISE EXCEPTION 'SERVICIOS: El evento "%" está %; no se pueden modificar sus servicios.',
            v_evento.nombre, v_evento.estado;
    END IF;

    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    END IF;

    IF TG_OP = 'UPDATE' AND NEW.evento_id <> OLD.evento_id THEN
        RAISE EXCEPTION 'SERVICIOS: Un servicio contratado no se puede trasladar a otro evento.';
    END IF;

    SELECT * INTO v_servicio FROM servicios WHERE id = NEW.servicio_id;

    IF TG_OP = 'INSERT' OR NEW.servicio_id <> OLD.servicio_id THEN
        IF NOT v_servicio.activo THEN
            RAISE EXCEPTION 'SERVICIOS: El servicio "%" no está disponible en el catálogo.', v_servicio.nombre;
        END IF;
        NEW.precio_unitario := v_servicio.precio_unitario; 
    ELSE
        NEW.precio_unitario := OLD.precio_unitario;    
    END IF;

    IF NEW.cantidad IS NULL THEN
        NEW.cantidad_automatica := true;
        NEW.cantidad := CASE v_servicio.unidad_cobro
                            WHEN 'Por persona' THEN v_evento.aforo_esperado
                            WHEN 'Por hora'    THEN fn_horas_cobro(v_evento.inicio, v_evento.fin)
                            ELSE 1 END;
    ELSE
        NEW.cantidad_automatica := false;
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_es_10_validar ON evento_servicios;
CREATE TRIGGER trg_es_10_validar
    BEFORE INSERT OR UPDATE OR DELETE ON evento_servicios
    FOR EACH ROW EXECUTE FUNCTION fn_trg_es_validar();


-- A3.c Actualiza el total del evento
CREATE OR REPLACE FUNCTION fn_trg_es_total()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_evento_id INTEGER := CASE WHEN TG_OP = 'DELETE' THEN OLD.evento_id ELSE NEW.evento_id END;
BEGIN
    IF current_setting('nexo.recalculando', true) = 'on' THEN
        RETURN NULL;  
    END IF;
    UPDATE eventos e
       SET valor_total = fn_valor_total(e.id, e.salon_id, e.inicio, e.fin)
     WHERE e.id = v_evento_id
       AND e.estado NOT IN ('Finalizado', 'Cancelado');
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_es_90_total ON evento_servicios;
CREATE TRIGGER trg_es_90_total
    AFTER INSERT OR UPDATE OR DELETE ON evento_servicios
    FOR EACH ROW EXECUTE FUNCTION fn_trg_es_total();

-- A2. Cupos y asistencia real (check-in)
CREATE OR REPLACE FUNCTION fn_validar_checkin(p_evento eventos, p_hora TIMESTAMP)
RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
    IF p_evento.estado IN ('Cancelado', 'Finalizado') THEN
        RAISE EXCEPTION 'CHECK-IN: El evento "%" está %; no admite registro de asistencia.',
            p_evento.nombre, p_evento.estado;
    END IF;
    IF p_hora < p_evento.inicio - INTERVAL '1 hour' OR p_hora > p_evento.fin THEN
        RAISE EXCEPTION 'CHECK-IN: Solo se permite ingresar entre % y % (hora indicada: %).',
            fn_fmt(p_evento.inicio - INTERVAL '1 hour'), fn_fmt(p_evento.fin), fn_fmt(p_hora);
    END IF;
END $$;

CREATE OR REPLACE FUNCTION fn_trg_inscripciones()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_evento    eventos%ROWTYPE;
    v_inscritos INTEGER;
    v_nombre    TEXT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT * INTO v_evento FROM eventos WHERE id = NEW.evento_id FOR UPDATE;

        IF v_evento.estado IN ('Cancelado', 'Finalizado') THEN
            RAISE EXCEPTION 'INSCRIPCIÓN: El evento "%" está %; no admite inscripciones.',
                v_evento.nombre, v_evento.estado;
        END IF;

        SELECT COUNT(*) INTO v_inscritos FROM inscripciones WHERE evento_id = NEW.evento_id;
        IF v_inscritos >= v_evento.aforo_esperado THEN
            RAISE EXCEPTION 'CUPO: El evento "%" alcanzó su aforo contratado (% personas).',
                v_evento.nombre, v_evento.aforo_esperado;
        END IF;

        IF NEW.fecha_checkin IS NOT NULL THEN
            PERFORM fn_validar_checkin(v_evento, NEW.fecha_checkin);
        END IF;
        RETURN NEW;
    END IF;

    -- UPDATE
    IF NEW.evento_id <> OLD.evento_id OR NEW.asistente_id <> OLD.asistente_id THEN
        RAISE EXCEPTION 'INSCRIPCIÓN: Una inscripción no se puede trasladar; cree una nueva.';
    END IF;

    IF NEW.fecha_checkin IS DISTINCT FROM OLD.fecha_checkin THEN
        SELECT * INTO v_evento FROM eventos WHERE id = NEW.evento_id;
        IF OLD.fecha_checkin IS NOT NULL THEN
            SELECT nombre INTO v_nombre FROM asistentes WHERE id = NEW.asistente_id;
            RAISE EXCEPTION 'CHECK-IN: % ya registró su ingreso al evento "%" (%). Solo se permite una vez.',
                v_nombre, v_evento.nombre, fn_fmt(OLD.fecha_checkin);
        END IF;
        PERFORM fn_validar_checkin(v_evento, NEW.fecha_checkin);
    END IF;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_inscripciones_10_cupo_checkin ON inscripciones;
CREATE TRIGGER trg_inscripciones_10_cupo_checkin
    BEFORE INSERT OR UPDATE ON inscripciones
    FOR EACH ROW EXECUTE FUNCTION fn_trg_inscripciones();

-- A4 (parte 2). Auditoría de estado, salón y horario
CREATE OR REPLACE FUNCTION fn_trg_eventos_auditoria()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_usuario TEXT := fn_usuario_app();
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO auditoria_eventos (evento_id, campo, valor_anterior, valor_nuevo, usuario)
        VALUES (NEW.id, 'creacion', NULL, NEW.estado, v_usuario);
        RETURN NULL;
    END IF;

    IF NEW.estado <> OLD.estado THEN
        INSERT INTO auditoria_eventos (evento_id, campo, valor_anterior, valor_nuevo, usuario)
        VALUES (NEW.id, 'estado', OLD.estado, NEW.estado, v_usuario);
    END IF;
    IF NEW.salon_id <> OLD.salon_id THEN
        INSERT INTO auditoria_eventos (evento_id, campo, valor_anterior, valor_nuevo, usuario)
        VALUES (NEW.id, 'salon',
                (SELECT nombre FROM salones WHERE id = OLD.salon_id),
                (SELECT nombre FROM salones WHERE id = NEW.salon_id), v_usuario);
    END IF;
    IF NEW.inicio <> OLD.inicio THEN
        INSERT INTO auditoria_eventos (evento_id, campo, valor_anterior, valor_nuevo, usuario)
        VALUES (NEW.id, 'inicio', fn_fmt(OLD.inicio), fn_fmt(NEW.inicio), v_usuario);
    END IF;
    IF NEW.fin <> OLD.fin THEN
        INSERT INTO auditoria_eventos (evento_id, campo, valor_anterior, valor_nuevo, usuario)
        VALUES (NEW.id, 'fin', fn_fmt(OLD.fin), fn_fmt(NEW.fin), v_usuario);
    END IF;
    RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS trg_eventos_90_auditoria ON eventos;
CREATE TRIGGER trg_eventos_90_auditoria
    AFTER INSERT OR UPDATE ON eventos
    FOR EACH ROW EXECUTE FUNCTION fn_trg_eventos_auditoria();

-- Staff: evita ciclos en la jerarquía
CREATE OR REPLACE FUNCTION fn_trg_staff_jerarquia()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
DECLARE
    v_actual INTEGER := NEW.jefe_id;
    v_pasos  INTEGER := 0;
BEGIN
    WHILE v_actual IS NOT NULL AND v_pasos < 100 LOOP
        IF v_actual = NEW.id THEN
            RAISE EXCEPTION 'JERARQUÍA: Asignar ese jefe a "%" crearía un ciclo en la organización.', NEW.nombre;
        END IF;
        SELECT jefe_id INTO v_actual FROM staff WHERE id = v_actual;
        v_pasos := v_pasos + 1;
    END LOOP;
    RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_staff_10_jerarquia ON staff;
CREATE TRIGGER trg_staff_10_jerarquia
    BEFORE INSERT OR UPDATE OF jefe_id ON staff
    FOR EACH ROW EXECUTE FUNCTION fn_trg_staff_jerarquia();

-- A5. Salones disponibles
CREATE OR REPLACE FUNCTION fn_salones_disponibles(
    p_inicio TIMESTAMP, p_fin TIMESTAMP, p_aforo INTEGER, p_excluir_evento INTEGER DEFAULT NULL)
RETURNS TABLE (salon_id INTEGER, nombre VARCHAR, tamano VARCHAR, capacidad INTEGER,
               precio_hora NUMERIC, costo_estimado NUMERIC)
LANGUAGE plpgsql STABLE AS $$
#variable_conflict use_column
BEGIN
    IF p_fin <= p_inicio THEN
        RAISE EXCEPTION 'HORARIO: La fecha/hora de fin debe ser posterior a la de inicio.';
    END IF;
    IF p_aforo IS NULL OR p_aforo <= 0 THEN
        RAISE EXCEPTION 'CAPACIDAD: El aforo debe ser mayor que cero.';
    END IF;

    RETURN QUERY
    SELECT s.id, s.nombre, s.tamano, s.capacidad, s.precio_hora,
           ROUND(s.precio_hora * fn_horas(p_inicio, p_fin), 2)
    FROM salones s
    WHERE s.activo
      AND s.capacidad >= p_aforo
      AND NOT EXISTS (SELECT 1 FROM fn_evento_en_conflicto(s.id, p_inicio, p_fin, p_excluir_evento))
    ORDER BY s.capacidad, s.precio_hora;
END $$;
