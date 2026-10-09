INSERT INTO salones (nombre, tamano, capacidad, precio_hora) VALUES
    ('Salón Orquídea',      'Pequeño',   40,  250000),
    ('Salón Heliconia',     'Pequeño',   60,  320000),
    ('Salón Guayacán',      'Mediano',  150,  650000),
    ('Salón Ceiba',         'Mediano',  200,  800000),
    ('Gran Salón Cóndor',   'Grande',   600, 1800000),
    ('Auditorio Principal', 'Grande',  1000, 2500000)
ON CONFLICT (nombre) DO NOTHING;

INSERT INTO servicios (nombre, categoria, unidad_cobro, precio_unitario) VALUES
    ('Estación de agua',                            'Bebidas',       'Por persona',   3000),
    ('Estación de café',                            'Bebidas',       'Por persona',   6500),
    ('Refrigerio económico',                        'Refrigerios',   'Por persona',  12000),
    ('Refrigerio medio',                            'Refrigerios',   'Por persona',  22000),
    ('Refrigerio alto',                             'Refrigerios',   'Por persona',  38000),
    ('Sonido básico (2 micrófonos + parlantes)',    'Audiovisuales', 'Por hora',    120000),
    ('Sonido profesional (consola + 6 micrófonos)', 'Audiovisuales', 'Por hora',    350000),
    ('Multimedia (proyector + pantalla)',           'Audiovisuales', 'Por hora',     90000),
    ('Streaming y grabación',                       'Audiovisuales', 'Por hora',    450000)
ON CONFLICT (nombre) DO NOTHING;
