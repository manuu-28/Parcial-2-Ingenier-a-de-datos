
CREATE OR REPLACE FUNCTION pg_temp.srv(p_nombre TEXT) RETURNS INTEGER LANGUAGE sql AS
$$ SELECT id FROM servicios WHERE nombre = p_nombre $$;

CREATE OR REPLACE FUNCTION pg_temp.salon(p_nombre TEXT) RETURNS INTEGER LANGUAGE sql AS
$$ SELECT id FROM salones WHERE nombre = p_nombre $$;

CREATE OR REPLACE FUNCTION pg_temp.staff(p_correo TEXT) RETURNS INTEGER LANGUAGE sql AS
$$ SELECT id FROM staff WHERE correo = p_correo $$;

CREATE OR REPLACE FUNCTION pg_temp.cliente(p_doc TEXT) RETURNS INTEGER LANGUAGE sql AS
$$ SELECT id FROM clientes WHERE documento = p_doc $$;

CREATE OR REPLACE FUNCTION pg_temp.inscribir(p_evento INTEGER, p_desde INTEGER, p_cuantos INTEGER)
RETURNS VOID LANGUAGE sql AS $$
    INSERT INTO inscripciones (evento_id, asistente_id, fecha_inscripcion)
    SELECT p_evento, a.id, LOCALTIMESTAMP
    FROM (SELECT id FROM asistentes ORDER BY documento OFFSET p_desde - 1 LIMIT p_cuantos) a;
$$;

CREATE OR REPLACE FUNCTION pg_temp.checkin(p_evento INTEGER, p_cuantos INTEGER)
RETURNS VOID LANGUAGE sql AS $$
    UPDATE inscripciones i
       SET fecha_checkin = e.inicio - INTERVAL '30 minutes' + (x.rn % 45) * INTERVAL '1 minute'
      FROM eventos e,
           (SELECT id, ROW_NUMBER() OVER (ORDER BY asistente_id) AS rn
              FROM inscripciones WHERE evento_id = p_evento) x
     WHERE i.id = x.id AND x.rn <= p_cuantos AND e.id = i.evento_id;
$$;


DO $$
DECLARE
    e1 INT; e2 INT; e3 INT; e4 INT; e5 INT; e6 INT; e7 INT;
    e8 INT; e9 INT; e10 INT; e11 INT; e12 INT; e13 INT; e14 INT;
    v_coord1 INT; v_coord2 INT;
BEGIN
    IF EXISTS (SELECT 1 FROM clientes) THEN
        RAISE NOTICE 'Ya hay datos cargados: no se vuelve a ejecutar la carga.';
        RETURN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM salones) THEN
        RAISE EXCEPTION 'Primero arranque la API para crear tablas, triggers y catálogo.';
    END IF;

    PERFORM set_config('nexo.usuario', 'carga_inicial', true);

    -- -----------------------------------------------------------------
    -- Clientes (8): 5 empresas y 3 personas
    -- -----------------------------------------------------------------
    INSERT INTO clientes (tipo, documento, nombre, correo, telefono, fecha_registro) VALUES
        ('Empresa', '900123456-1', 'Logística Andina S.A.S.',     'eventos@logisticaandina.co', '6013001001', '2026-01-15'),
        ('Empresa', '900234567-2', 'CiberSegura Ltda.',           'contacto@cibersegura.co',    '6013002002', '2026-02-03'),
        ('Empresa', '900345678-3', 'Café de Origen S.A.',         'mercadeo@cafedeorigen.co',   '6043003003', '2026-02-20'),
        ('Empresa', '900456789-4', 'Laboratorios Solvida S.A.',   'academico@solvida.co',       '6013004004', '2026-03-11'),
        ('Persona', '1020304050',  'Mariana Martínez Ríos',       'mariana.martinez@gmail.com', '3104005005', '2026-04-02'),
        ('Persona', '79888777',    'Jorge Iván Peñaloza',         'jorge.penaloza@gmail.com',   '3156006006', '2026-05-19'),
        ('Persona', '52111222',    'Lucía Fernández Páramo',      'lucia.fernandez@gmail.com',  '3007007007', '2026-06-08'),
        ('Empresa', '901567890-5', 'Wayuu Emprende S.A.S.',       'hola@wayuuemprende.co',      '6057008008', '2026-07-01');

    -- -----------------------------------------------------------------
    -- Staff (17) en 5 niveles. Se inserta de arriba hacia abajo.
    -- -----------------------------------------------------------------
    INSERT INTO staff (nombre, cargo, area, correo, fecha_ingreso, jefe_id) VALUES
        ('Laura Méndez', 'Directora General', 'Dirección', 'lmendez@nexo.co', '2015-02-01', NULL);
    INSERT INTO staff (nombre, cargo, area, correo, fecha_ingreso, jefe_id) VALUES
        ('Andrés Rojas',   'Gerente de Operaciones',         'Operaciones',        'arojas@nexo.co',  '2016-05-10', pg_temp.staff('lmendez@nexo.co')),
        ('Camila Vargas',  'Gerente Comercial',              'Comercial',          'cvargas@nexo.co', '2017-03-01', pg_temp.staff('lmendez@nexo.co')),
        ('Felipe Arango',  'Gerente de Alimentos y Bebidas', 'Alimentos y Bebidas','farango@nexo.co', '2018-08-15', pg_temp.staff('lmendez@nexo.co'));
    INSERT INTO staff (nombre, cargo, area, correo, fecha_ingreso, jefe_id) VALUES
        ('Diana Torres',   'Jefe de Logística',              'Logística',          'dtorres@nexo.co', '2019-01-20', pg_temp.staff('arojas@nexo.co')),
        ('Mauricio Peña',  'Jefe de Audiovisuales',          'Audiovisuales',      'mpena@nexo.co',   '2019-06-03', pg_temp.staff('arojas@nexo.co')),
        ('Natalia Gómez',  'Jefe de Ventas Corporativas',    'Comercial',          'ngomez@nexo.co',  '2020-02-17', pg_temp.staff('cvargas@nexo.co')),
        ('Óscar Herrera',  'Jefe de Cocina',                 'Alimentos y Bebidas','oherrera@nexo.co','2020-09-01', pg_temp.staff('farango@nexo.co'));
    INSERT INTO staff (nombre, cargo, area, correo, fecha_ingreso, jefe_id) VALUES
        ('Julián Castro',  'Coordinador de Eventos',         'Operaciones',        'jcastro@nexo.co', '2021-04-12', pg_temp.staff('dtorres@nexo.co')),
        ('Paula Ríos',     'Coordinadora de Eventos',        'Operaciones',        'prios@nexo.co',   '2021-11-08', pg_temp.staff('dtorres@nexo.co')),
        ('Sara Pineda',    'Ejecutiva Comercial',            'Comercial',          'spineda@nexo.co', '2022-03-14', pg_temp.staff('ngomez@nexo.co')),
        ('Luis Cárdenas',  'Supervisor de Meseros',          'Alimentos y Bebidas','lcardenas@nexo.co','2022-07-25', pg_temp.staff('oherrera@nexo.co'));
    INSERT INTO staff (nombre, cargo, area, correo, fecha_ingreso, jefe_id) VALUES
        ('Kevin Morales',  'Auxiliar de Logística',          'Logística',          'kmorales@nexo.co','2023-02-06', pg_temp.staff('jcastro@nexo.co')),
        ('Jorge Salcedo',  'Auxiliar de Montaje',            'Logística',          'jsalcedo@nexo.co','2023-09-18', pg_temp.staff('prios@nexo.co')),
        ('Daniel Ortiz',   'Técnico de Sonido',              'Audiovisuales',      'dortiz@nexo.co',  '2023-05-22', pg_temp.staff('mpena@nexo.co')),
        ('Valentina Ruiz', 'Técnica de Multimedia',          'Audiovisuales',      'vruiz@nexo.co',   '2024-01-15', pg_temp.staff('mpena@nexo.co')),
        ('Andrea Quintero','Mesera',                         'Alimentos y Bebidas','aquintero@nexo.co','2024-06-03', pg_temp.staff('lcardenas@nexo.co'));

    v_coord1 := pg_temp.staff('jcastro@nexo.co');
    v_coord2 := pg_temp.staff('prios@nexo.co');

    -- -----------------------------------------------------------------
    -- Asistentes (60)
    -- -----------------------------------------------------------------
    INSERT INTO asistentes (documento, nombre, correo, empresa)
    SELECT (1000100000 + g)::TEXT,
           (ARRAY['Ana','Carlos','Daniela','Esteban','Gabriela','Héctor','Isabel','Juan','Karen','Luis',
                  'María','Nicolás','Olga','Pedro','Rosa'])[1 + (g - 1) % 15] || ' ' ||
           (ARRAY['Acosta','Bermúdez','Cifuentes','Duarte'])[1 + ((g - 1) / 15) % 4],
           'asistente' || g || '@correo.co',
           (ARRAY['Logística Andina','CiberSegura','Café de Origen','Solvida','Independiente','Universidad del Rosario'])[1 + g % 6]
    FROM generate_series(1, 60) AS g;

    -- -----------------------------------------------------------------
    -- EVENTOS PASADOS
    -- -----------------------------------------------------------------
    -- 1. Finalizado, tasa 80 % (24 de 30)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900123456-1'), pg_temp.salon('Salón Ceiba'), v_coord1,
            'Foro de Innovación Logística', 'Congreso', '2026-08-12 08:00', '2026-08-12 17:00', 150)
    RETURNING id INTO e1;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e1, pg_temp.srv('Estación de café'), NULL),
        (e1, pg_temp.srv('Refrigerio medio'), NULL),
        (e1, pg_temp.srv('Sonido profesional (consola + 6 micrófonos)'), NULL),
        (e1, pg_temp.srv('Multimedia (proyector + pantalla)'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e1;
    PERFORM pg_temp.inscribir(e1, 16, 30);
    PERFORM pg_temp.checkin(e1, 24);
    UPDATE eventos SET estado = 'Finalizado' WHERE id = e1;

    -- 2. Finalizado, tasa 71,11 % (32 de 45)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900234567-2'), pg_temp.salon('Salón Guayacán'), v_coord2,
            'Capacitación en Ciberseguridad', 'Seminario', '2026-09-10 08:00', '2026-09-10 12:00', 45)
    RETURNING id INTO e2;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e2, pg_temp.srv('Estación de café'), NULL),
        (e2, pg_temp.srv('Refrigerio económico'), NULL),
        (e2, pg_temp.srv('Multimedia (proyector + pantalla)'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e2;
    PERFORM pg_temp.inscribir(e2, 1, 45);
    PERFORM pg_temp.checkin(e2, 32);
    UPDATE eventos SET estado = 'Finalizado' WHERE id = e2;

    -- 3. Finalizado, termina después de medianoche, tasa 100 % (25 de 25)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900345678-3'), pg_temp.salon('Salón Heliconia'), v_coord1,
            'Lanzamiento Línea Café de Origen', 'Corporativo', '2026-09-18 18:00', '2026-09-19 01:00', 55)
    RETURNING id INTO e3;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e3, pg_temp.srv('Refrigerio alto'), NULL),
        (e3, pg_temp.srv('Sonido básico (2 micrófonos + parlantes)'), NULL),
        (e3, pg_temp.srv('Estación de agua'), 60);            -- cantidad explícita
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e3;
    PERFORM pg_temp.inscribir(e3, 36, 25);
    PERFORM pg_temp.checkin(e3, 25);
    UPDATE eventos SET estado = 'Finalizado' WHERE id = e3;

    -- 4. Finalizado sin inscritos (boda): tasa vacía
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('1020304050'), pg_temp.salon('Gran Salón Cóndor'), v_coord2,
            'Boda Martínez Ríos', 'Social', '2026-09-26 17:00', '2026-09-27 02:00', 250)
    RETURNING id INTO e4;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e4, pg_temp.srv('Refrigerio alto'), NULL),
        (e4, pg_temp.srv('Sonido profesional (consola + 6 micrófonos)'), NULL),
        (e4, pg_temp.srv('Streaming y grabación'), 4);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e4;
    UPDATE eventos SET estado = 'Finalizado' WHERE id = e4;

    -- 5. Cancelado (pasado)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('79888777'), pg_temp.salon('Salón Orquídea'), v_coord1,
            'Seminario de Finanzas Personales', 'Seminario', '2026-09-05 09:00', '2026-09-05 13:00', 30)
    RETURNING id INTO e5;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e5, pg_temp.srv('Estación de café'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e5;
    PERFORM pg_temp.inscribir(e5, 50, 8);
    UPDATE eventos SET estado = 'Cancelado' WHERE id = e5;

    -- 6. Confirmado y ya terminó: queda listo para FINALIZAR en vivo (tasa esperada 75 %)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900123456-1'), pg_temp.salon('Auditorio Principal'), v_coord2,
            'Feria Empresarial del Caribe', 'Feria', '2026-09-24 09:00', '2026-09-24 18:00', 800)
    RETURNING id INTO e6;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e6, pg_temp.srv('Estación de agua'), NULL),
        (e6, pg_temp.srv('Sonido profesional (consola + 6 micrófonos)'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e6;
    PERFORM pg_temp.inscribir(e6, 21, 40);
    PERFORM pg_temp.checkin(e6, 30);

    -- -----------------------------------------------------------------
    -- EVENTOS FUTUROS
    -- -----------------------------------------------------------------
    -- 7. Guayacán ocupado el 18-nov de 08:00 a 12:00 (para el ejemplo de A1)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900456789-4'), pg_temp.salon('Salón Guayacán'), v_coord1,
            'Jornada Científica Solvida', 'Congreso', '2026-11-18 08:00', '2026-11-18 12:00', 120)
    RETURNING id INTO e7;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e7, pg_temp.srv('Estación de café'), NULL),
        (e7, pg_temp.srv('Refrigerio medio'), NULL),
        (e7, pg_temp.srv('Multimedia (proyector + pantalla)'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e7;
    PERFORM pg_temp.inscribir(e7, 1, 15);

    -- 8. Cupo lleno: 20 inscritos de 20 (para el ejemplo de A2)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('52111222'), pg_temp.salon('Salón Orquídea'), v_coord2,
            'Club de Lectura Páramo', 'Social', '2026-11-18 16:00', '2026-11-18 18:30', 20)
    RETURNING id INTO e8;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e8, pg_temp.srv('Estación de café'), NULL),
        (e8, pg_temp.srv('Refrigerio económico'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e8;
    PERFORM pg_temp.inscribir(e8, 41, 20);

    -- 9. Cotizado y reprogramado (deja rastro en la auditoría)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('901567890-5'), pg_temp.salon('Salón Ceiba'), v_coord1,
            'Conferencia IA aplicada a Ventas', 'Conferencia', '2026-11-25 14:00', '2026-11-25 17:00', 180)
    RETURNING id INTO e9;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e9, pg_temp.srv('Estación de agua'), NULL),
        (e9, pg_temp.srv('Sonido básico (2 micrófonos + parlantes)'), NULL),
        (e9, pg_temp.srv('Streaming y grabación'), NULL);
    PERFORM set_config('nexo.usuario', 'spineda', true);
    UPDATE eventos SET fin = '2026-11-25 18:00' WHERE id = e9;   -- una hora más: recalcula servicios por hora
    PERFORM set_config('nexo.usuario', 'carga_inicial', true);

    -- 10. Auditorio ocupado el 18-nov (para el ejemplo de A5)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900345678-3'), pg_temp.salon('Auditorio Principal'), v_coord2,
            'Asamblea General de Accionistas', 'Corporativo', '2026-11-18 07:00', '2026-11-18 13:00', 700)
    RETURNING id INTO e10;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e10, pg_temp.srv('Estación de agua'), NULL),
        (e10, pg_temp.srv('Refrigerio económico'), NULL),
        (e10, pg_temp.srv('Sonido profesional (consola + 6 micrófonos)'), NULL),
        (e10, pg_temp.srv('Streaming y grabación'), NULL);

    -- 11. Confirmado, cruza la medianoche
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900123456-1'), pg_temp.salon('Gran Salón Cóndor'), v_coord1,
            'Cena de Fin de Año Logística Andina', 'Social', '2026-12-12 19:00', '2026-12-13 01:00', 500)
    RETURNING id INTO e11;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e11, pg_temp.srv('Refrigerio alto'), NULL),
        (e11, pg_temp.srv('Sonido profesional (consola + 6 micrófonos)'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e11;

    -- 12. Cancelado (futuro): libera el Salón Heliconia
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900456789-4'), pg_temp.salon('Salón Heliconia'), v_coord2,
            'Taller de Liderazgo Solvida', 'Seminario', '2026-10-20 08:00', '2026-10-20 12:00', 40)
    RETURNING id INTO e12;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e12, pg_temp.srv('Refrigerio medio'), NULL);
    UPDATE eventos SET estado = 'Cancelado' WHERE id = e12;

    -- 13. Cotizado con cambio de salón (auditoría)
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('901567890-5'), pg_temp.salon('Salón Ceiba'), v_coord1,
            'Expo Emprendimiento Wayuu', 'Feria', '2026-10-15 09:00', '2026-10-15 17:00', 180)
    RETURNING id INTO e13;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e13, pg_temp.srv('Estación de agua'), NULL),
        (e13, pg_temp.srv('Sonido básico (2 micrófonos + parlantes)'), NULL);
    PERFORM set_config('nexo.usuario', 'cvargas', true);
    UPDATE eventos SET salon_id = pg_temp.salon('Gran Salón Cóndor'), aforo_esperado = 400 WHERE id = e13;
    PERFORM set_config('nexo.usuario', 'carga_inicial', true);

    -- 14. Confirmado en pocos días
    INSERT INTO eventos (cliente_id, salon_id, coordinador_id, nombre, tipo, inicio, fin, aforo_esperado)
    VALUES (pg_temp.cliente('900234567-2'), pg_temp.salon('Salón Orquídea'), v_coord2,
            'Seminario de Normativa Tributaria', 'Seminario', '2026-10-08 14:00', '2026-10-08 17:00', 35)
    RETURNING id INTO e14;
    INSERT INTO evento_servicios (evento_id, servicio_id, cantidad) VALUES
        (e14, pg_temp.srv('Estación de café'), NULL),
        (e14, pg_temp.srv('Multimedia (proyector + pantalla)'), NULL);
    UPDATE eventos SET estado = 'Confirmado' WHERE id = e14;
    PERFORM pg_temp.inscribir(e14, 30, 10);

    RAISE NOTICE 'Carga terminada: % clientes, % staff, % eventos, % asistentes, % inscripciones.',
        (SELECT COUNT(*) FROM clientes), (SELECT COUNT(*) FROM staff), (SELECT COUNT(*) FROM eventos),
        (SELECT COUNT(*) FROM asistentes), (SELECT COUNT(*) FROM inscripciones);
END $$;
