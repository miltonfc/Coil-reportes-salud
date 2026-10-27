-- =====================================================================
--  Proyecto COIL · UCompensar (Colombia) – UNICDA (República Dominicana)
--  Sistema de reportes de salud entre veredas y hospital rural
--  Actividad 4 · Modelo relacional – script de creación (SQLite 3)
--
--  Uso:   sqlite3 reportes_salud.db < schema_sqlite.sql
--         sqlite3 reportes_salud.db < datos_prueba.sql
--  Notas:
--   * Fechas en texto ISO 8601 (AAAA-MM-DD / AAAA-MM-DDTHH:MM).
--   * Booleanos como INTEGER 0/1.
--   * Para PostgreSQL (Neon) ver las equivalencias al final del archivo.
-- =====================================================================
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------
-- 1. Catálogos y actores
-- ---------------------------------------------------------------------
CREATE TABLE hospital (
    id_hospital     TEXT PRIMARY KEY,                       -- H-CO, H-RD
    nombre          TEXT NOT NULL,
    pais            TEXT NOT NULL CHECK (pais IN ('CO', 'RD')),
    nivel_atencion  TEXT NOT NULL DEFAULT 'Primer nivel'
);

-- Vereda (Colombia) o paraje (República Dominicana): unidad rural de origen del reporte
CREATE TABLE vereda (
    id_vereda       TEXT PRIMARY KEY,                       -- V-CO-01 …
    nombre          TEXT NOT NULL,
    tipo_division   TEXT NOT NULL CHECK (tipo_division IN ('Vereda', 'Paraje')),
    id_hospital     TEXT NOT NULL REFERENCES hospital (id_hospital),
    distancia_km    REAL CHECK (distancia_km >= 0),
    conectividad    TEXT NOT NULL CHECK (conectividad IN ('Buena', 'Intermitente', 'Sin señal'))
);

-- Personal: promotor (en la vereda), enfermería y médico (en el hospital)
CREATE TABLE personal_salud (
    id_personal     TEXT PRIMARY KEY,
    nombre          TEXT NOT NULL,
    rol             TEXT NOT NULL CHECK (rol IN ('Promotor', 'Enfermería', 'Médico')),
    id_hospital     TEXT REFERENCES hospital (id_hospital),
    id_vereda       TEXT REFERENCES vereda (id_vereda),
    CHECK ((rol = 'Promotor' AND id_vereda IS NOT NULL) OR (rol <> 'Promotor' AND id_hospital IS NOT NULL))
);

-- Catálogo de diagnósticos (CIE-10; columna para la codificación dual CIE-11 de Colombia)
CREATE TABLE diagnostico (
    codigo_cie10    TEXT PRIMARY KEY,
    descripcion     TEXT NOT NULL,
    codigo_cie11    TEXT                                    -- por mapear (Res. 1442 de 2024, Colombia)
);

-- Reglas de puntaje editables (equivalente a la hoja «Criterios» del Excel)
CREATE TABLE criterio_alerta (
    variable        TEXT NOT NULL CHECK (variable IN ('IMC', 'PA', 'FC', 'FR', 'SpO2')),
    categoria       TEXT NOT NULL,
    puntos          INTEGER NOT NULL CHECK (puntos BETWEEN 0 AND 3),
    PRIMARY KEY (variable, categoria)
);

-- ---------------------------------------------------------------------
-- 2. Paciente (BD1) – datos que no cambian entre reportes
-- ---------------------------------------------------------------------
CREATE TABLE paciente (
    id_paciente      TEXT PRIMARY KEY CHECK (id_paciente GLOB 'P-[0-9][0-9][0-9]'),
    nombre           TEXT NOT NULL CHECK (length(trim(nombre)) > 0),
    fecha_nacimiento TEXT NOT NULL,                         -- la edad se calcula, no se guarda
    sexo             TEXT NOT NULL CHECK (sexo IN ('M', 'F')),
    grupo_sanguineo  TEXT NOT NULL CHECK (grupo_sanguineo IN ('A', 'B', 'AB', 'O')),
    factor_rh        TEXT NOT NULL CHECK (factor_rh IN ('+', '-')),
    id_vereda        TEXT NOT NULL REFERENCES vereda (id_vereda),
    consentimiento   INTEGER NOT NULL CHECK (consentimiento IN (0, 1)),
    fecha_registro   TEXT NOT NULL
);

-- ---------------------------------------------------------------------
-- 3. Reporte (BD3 + datos de envío) – un paciente tiene N reportes
-- ---------------------------------------------------------------------
CREATE TABLE reporte (
    id_reporte           INTEGER PRIMARY KEY AUTOINCREMENT,
    id_paciente          TEXT NOT NULL REFERENCES paciente (id_paciente),
    id_promotor          TEXT NOT NULL REFERENCES personal_salud (id_personal),
    tipo_reporte         TEXT NOT NULL CHECK (tipo_reporte IN ('Inicial', 'Control')),
    fecha_reporte        TEXT NOT NULL CHECK (fecha_reporte >= '2020-01-01'),
    motivo_consulta      TEXT NOT NULL CHECK (length(motivo_consulta) <= 100),
    requiere_seguimiento INTEGER NOT NULL CHECK (requiere_seguimiento IN (0, 1)),
    codigo_cie10         TEXT REFERENCES diagnostico (codigo_cie10),
    puntaje_alerta       INTEGER NOT NULL CHECK (puntaje_alerta BETWEEN 0 AND 10),
    prioridad_sugerida   TEXT NOT NULL CHECK (prioridad_sugerida IN ('Alta', 'Media', 'Baja')),
    prioridad_asignada   TEXT CHECK (prioridad_asignada IN ('Alta', 'Media', 'Baja')),
    canal                TEXT NOT NULL CHECK (canal IN ('Sincrónico', 'Asincrónico')),
    estado_envio         TEXT NOT NULL DEFAULT 'Pendiente' CHECK (estado_envio IN ('Pendiente', 'Enviado')),
    intentos_envio       INTEGER NOT NULL DEFAULT 0 CHECK (intentos_envio >= 0),
    fecha_envio          TEXT,
    estado_reporte       TEXT NOT NULL DEFAULT 'Por enviar'
                         CHECK (estado_reporte IN ('Por enviar', 'Recibido', 'En revisión', 'Atendido')),
    -- reglas de negocio del diccionario de variables
    CHECK (requiere_seguimiento = 0 OR codigo_cie10 IS NOT NULL),          -- enfermedad: condicional
    CHECK (estado_envio = 'Enviado' OR (fecha_envio IS NULL AND estado_reporte = 'Por enviar')),
    CHECK (estado_reporte <> 'Atendido' OR prioridad_asignada IS NOT NULL)
);

-- Signos vitales del reporte (BD2) – relación 1:1 con reporte
CREATE TABLE signos_vitales (
    id_reporte   INTEGER PRIMARY KEY REFERENCES reporte (id_reporte) ON DELETE CASCADE,
    talla_cm     INTEGER NOT NULL CHECK (talla_cm BETWEEN 40 AND 250),
    peso_kg      REAL    NOT NULL CHECK (peso_kg BETWEEN 2 AND 300),
    fc_lpm       INTEGER NOT NULL CHECK (fc_lpm BETWEEN 30 AND 220),
    fr_rpm       INTEGER NOT NULL CHECK (fr_rpm BETWEEN 5 AND 60),
    pas_mmhg     INTEGER NOT NULL CHECK (pas_mmhg BETWEEN 60 AND 260),
    pad_mmhg     INTEGER NOT NULL CHECK (pad_mmhg BETWEEN 30 AND 160),
    spo2_pct     INTEGER CHECK (spo2_pct BETWEEN 50 AND 100),            -- opcional
    ph_orina     REAL    CHECK (ph_orina BETWEEN 4.5 AND 8.5),           -- opcional
    CHECK (pas_mmhg > pad_mmhg)
);

-- ---------------------------------------------------------------------
-- 4. Respuesta del hospital
-- ---------------------------------------------------------------------
CREATE TABLE observacion_medica (
    id_observacion  INTEGER PRIMARY KEY AUTOINCREMENT,
    id_reporte      INTEGER NOT NULL REFERENCES reporte (id_reporte),
    id_profesional  TEXT NOT NULL REFERENCES personal_salud (id_personal),
    fecha_hora      TEXT NOT NULL,
    conducta        TEXT NOT NULL CHECK (conducta IN ('Sin conducta adicional', 'Control en vereda',
                                                     'Cita en hospital', 'Teleconsulta', 'Remisión urgente')),
    observacion     TEXT NOT NULL
);

CREATE TABLE notificacion (
    id_notificacion INTEGER PRIMARY KEY AUTOINCREMENT,
    id_reporte      INTEGER NOT NULL REFERENCES reporte (id_reporte),
    medio           TEXT NOT NULL CHECK (medio IN ('SMS', 'Llamada', 'WhatsApp', 'Visita del promotor')),
    fecha_hora      TEXT NOT NULL,
    entregada       INTEGER NOT NULL DEFAULT 0 CHECK (entregada IN (0, 1))
);

-- ---------------------------------------------------------------------
-- 5. Índices para las consultas frecuentes
-- ---------------------------------------------------------------------
CREATE INDEX ix_paciente_vereda   ON paciente (id_vereda);
CREATE INDEX ix_reporte_paciente  ON reporte (id_paciente, fecha_reporte);
CREATE INDEX ix_reporte_bandeja   ON reporte (estado_reporte, prioridad_sugerida);
CREATE INDEX ix_reporte_envio     ON reporte (estado_envio);
CREATE INDEX ix_obs_reporte       ON observacion_medica (id_reporte);

-- ---------------------------------------------------------------------
-- 6. Vistas = los tres reportes definidos en la Actividad 2
-- ---------------------------------------------------------------------
-- 6.1 Bandeja del hospital: lo primero que se ve (prioridad, luego antigüedad)
CREATE VIEW v_bandeja_hospital AS
SELECT r.id_reporte, h.pais, v.nombre AS vereda, v.conectividad,
       r.prioridad_sugerida, r.canal, r.estado_reporte, r.fecha_reporte,
       p.id_paciente, p.nombre,
       CAST((julianday(r.fecha_reporte) - julianday(p.fecha_nacimiento)) / 365.25 AS INTEGER) AS edad,
       s.pas_mmhg || '/' || s.pad_mmhg AS presion, s.fc_lpm, s.fr_rpm, s.spo2_pct,
       r.puntaje_alerta, r.motivo_consulta
FROM reporte r
JOIN paciente p       ON p.id_paciente = r.id_paciente
JOIN vereda v         ON v.id_vereda = p.id_vereda
JOIN hospital h       ON h.id_hospital = v.id_hospital
JOIN signos_vitales s ON s.id_reporte = r.id_reporte
WHERE r.estado_reporte IN ('Recibido', 'En revisión')
ORDER BY CASE r.prioridad_sugerida WHEN 'Alta' THEN 1 WHEN 'Media' THEN 2 ELSE 3 END, r.fecha_reporte;

-- 6.2 Reporte clínico individual (profesional de salud)
CREATE VIEW v_reporte_clinico AS
SELECT r.id_reporte, r.tipo_reporte, r.fecha_reporte,
       p.id_paciente, p.nombre, p.sexo,
       CAST((julianday(r.fecha_reporte) - julianday(p.fecha_nacimiento)) / 365.25 AS INTEGER) AS edad,
       v.nombre AS vereda, p.grupo_sanguineo || p.factor_rh AS tipo_sangre,
       s.talla_cm, s.peso_kg, ROUND(s.peso_kg / ((s.talla_cm / 100.0) * (s.talla_cm / 100.0)), 1) AS imc,
       s.fc_lpm, s.fr_rpm, s.pas_mmhg, s.pad_mmhg, s.spo2_pct, s.ph_orina,
       r.puntaje_alerta, r.prioridad_sugerida, r.prioridad_asignada
FROM reporte r
JOIN paciente p       ON p.id_paciente = r.id_paciente
JOIN vereda v         ON v.id_vereda = p.id_vereda
JOIN signos_vitales s ON s.id_reporte = r.id_reporte;

-- 6.3 Reporte de seguimiento (gestión del caso)
CREATE VIEW v_reporte_seguimiento AS
SELECT r.id_reporte, p.id_paciente, p.nombre, r.fecha_reporte, r.motivo_consulta,
       r.requiere_seguimiento, d.codigo_cie10, d.descripcion AS enfermedad,
       r.prioridad_sugerida, r.prioridad_asignada, r.canal, r.estado_envio, r.estado_reporte,
       o.conducta, o.observacion, o.fecha_hora AS fecha_atencion, n.medio AS notificado_por
FROM reporte r
JOIN paciente p              ON p.id_paciente = r.id_paciente
LEFT JOIN diagnostico d      ON d.codigo_cie10 = r.codigo_cie10
LEFT JOIN observacion_medica o ON o.id_reporte = r.id_reporte
LEFT JOIN notificacion n     ON n.id_reporte = r.id_reporte;

-- 6.4 Reporte gerencial agregado: SIN nombre ni ID (datos sensibles)
CREATE VIEW v_reporte_gerencial AS
SELECT h.pais, v.nombre AS vereda, substr(r.fecha_reporte, 1, 7) AS mes,
       COUNT(*)                                                AS reportes,
       SUM(r.prioridad_sugerida = 'Alta')                      AS prioridad_alta,
       SUM(r.prioridad_sugerida = 'Media')                     AS prioridad_media,
       SUM(r.prioridad_sugerida = 'Baja')                      AS prioridad_baja,
       SUM(r.requiere_seguimiento)                             AS con_seguimiento,
       SUM(r.estado_envio = 'Pendiente')                       AS pendientes_envio,
       ROUND(AVG(s.pas_mmhg), 1)                               AS pas_promedio
FROM reporte r
JOIN paciente p       ON p.id_paciente = r.id_paciente
JOIN vereda v         ON v.id_vereda = p.id_vereda
JOIN hospital h       ON h.id_hospital = v.id_hospital
JOIN signos_vitales s ON s.id_reporte = r.id_reporte
GROUP BY h.pais, v.nombre, mes;

-- =====================================================================
--  Equivalencias para PostgreSQL (Neon / Azure / AWS):
--   INTEGER PRIMARY KEY AUTOINCREMENT -> INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY
--   TEXT de fechas                    -> DATE / TIMESTAMP
--   INTEGER 0/1                       -> BOOLEAN
--   GLOB 'P-[0-9][0-9][0-9]'          -> ~ '^P-[0-9]{3}$'
--   julianday(a) - julianday(b)       -> date_part('year', age(a, b))
--   SUM(condición)                    -> COUNT(*) FILTER (WHERE condición)
-- =====================================================================
