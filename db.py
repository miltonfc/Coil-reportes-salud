"""Acceso a la base SQLite (estructura de la Actividad 4)."""
import csv
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from pathlib import Path

import pandas as pd

CARPETA = Path(__file__).resolve().parent / "base"
BASE = Path(os.environ.get("COIL_DB", CARPETA / "reportes_salud.db"))  # COIL_DB: base alternativa para pruebas


def crear_base(con_datos_prueba: bool = True) -> None:
    """Crea (o reinicia) la base desde los scripts SQL."""
    if BASE.exists():
        BASE.unlink()
    if CLAVES_DEMO.exists():
        CLAVES_DEMO.unlink()
    con = sqlite3.connect(BASE)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript((CARPETA / "schema_sqlite.sql").read_text(encoding="utf-8"))
    if con_datos_prueba:
        con.executescript((CARPETA / "datos_prueba.sql").read_text(encoding="utf-8"))
    _asegurar_credenciales(con)
    con.commit()
    con.close()


# ---------------- Credenciales (una clave por paciente, guardada con hash) ----------------
CLAVES_DEMO = BASE.parent / "claves_demo.csv"   # solo para la demostración académica
CLAVE_DEMO_P001 = "Usuario123!"                 # clave conocida para la demo; el resto es aleatoria
ITERACIONES = 200_000


def _hash(clave: str, sal: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", clave.encode("utf-8"), sal, ITERACIONES).hex()


def _guardar_clave(con, pid: str, clave: str) -> None:
    sal = secrets.token_bytes(16)
    con.execute("INSERT OR REPLACE INTO credencial (id_paciente, sal, hash_clave, actualizada) VALUES (?, ?, ?, ?)",
                (pid, sal.hex(), _hash(clave, sal), ahora()))


def nueva_clave() -> str:
    """Clave temporal legible: Salud-xxxxxx (6 caracteres aleatorios)."""
    return "Salud-" + secrets.token_hex(3)


def _asegurar_credenciales(con) -> None:
    """Crea la tabla de credenciales si no existe y da clave a los pacientes que no la tengan.
    Las claves generadas se anotan en claves_demo.csv para poder hacer la demostración."""
    con.execute("""CREATE TABLE IF NOT EXISTS credencial (
                       id_paciente TEXT PRIMARY KEY REFERENCES paciente (id_paciente) ON DELETE CASCADE,
                       sal         TEXT NOT NULL,
                       hash_clave  TEXT NOT NULL,
                       actualizada TEXT NOT NULL)""")
    sin_clave = [r[0] for r in con.execute(
        "SELECT id_paciente FROM paciente WHERE id_paciente NOT IN (SELECT id_paciente FROM credencial) ORDER BY id_paciente")]
    if not sin_clave:
        return
    nuevas = []
    for pid in sin_clave:
        clave = CLAVE_DEMO_P001 if pid == "P-001" else nueva_clave()
        _guardar_clave(con, pid, clave)
        nuevas.append((pid, clave))
    escribir_encabezado = not CLAVES_DEMO.exists()
    with open(CLAVES_DEMO, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if escribir_encabezado:
            w.writerow(["id_paciente", "clave_temporal"])
        w.writerows(nuevas)


_credenciales_listas = False


@contextmanager
def conexion():
    if not BASE.exists():
        crear_base()
    global _credenciales_listas
    con = sqlite3.connect(BASE)
    con.execute("PRAGMA foreign_keys = ON")
    con.row_factory = sqlite3.Row
    if not _credenciales_listas:          # bases creadas con una versión anterior
        _asegurar_credenciales(con)
        con.commit()
        _credenciales_listas = True
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


ZONA = ZoneInfo(os.environ.get("COIL_TZ", "America/Bogota"))   # los servidores en la nube suelen estar en UTC


def ahora() -> str:
    return datetime.now(ZONA).replace(tzinfo=None).isoformat(timespec="minutes")


def hoy() -> date:
    return datetime.now(ZONA).date()


def tabla(sql: str, params: tuple = ()) -> pd.DataFrame:
    with conexion() as con:
        return pd.read_sql_query(sql, con, params=params)


def uno(sql: str, params: tuple = ()):
    with conexion() as con:
        return con.execute(sql, params).fetchone()


# ---------------- Catálogos ----------------
def veredas() -> pd.DataFrame:
    return tabla("""SELECT v.*, h.pais, h.nombre AS hospital FROM vereda v
                    JOIN hospital h USING (id_hospital) ORDER BY h.pais, v.nombre""")


def diagnosticos() -> pd.DataFrame:
    return tabla("SELECT codigo_cie10, descripcion FROM diagnostico ORDER BY codigo_cie10")


def puntos_criterio() -> dict:
    with conexion() as con:
        return {(r["variable"], r["categoria"]): r["puntos"] for r in con.execute("SELECT * FROM criterio_alerta")}


def profesionales(id_hospital: str) -> pd.DataFrame:
    return tabla("SELECT id_personal, nombre, rol FROM personal_salud WHERE id_hospital = ? ORDER BY rol DESC, nombre",
                 (id_hospital,))


def promotor_de(id_vereda: str) -> str:
    r = uno("SELECT id_personal FROM personal_salud WHERE rol = 'Promotor' AND id_vereda = ?", (id_vereda,))
    return r["id_personal"]


# ---------------- Módulo 1: pacientes ----------------
def siguiente_id_paciente() -> str:
    r = uno("SELECT MAX(CAST(substr(id_paciente, 3) AS INTEGER)) AS n FROM paciente")
    return f"P-{(r['n'] or 0) + 1:03d}"


def registrar_paciente(nombre, fecha_nacimiento, sexo, grupo, rh, id_vereda, consentimiento) -> str:
    """Registra al paciente y le crea una clave temporal propia. Devuelve (código, clave)."""
    pid = siguiente_id_paciente()
    clave = nueva_clave()
    with conexion() as con:
        con.execute("""INSERT INTO paciente (id_paciente, nombre, fecha_nacimiento, sexo, grupo_sanguineo, factor_rh,
                       id_vereda, consentimiento, fecha_registro) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (pid, nombre.strip(), fecha_nacimiento.isoformat(), sexo, grupo, rh, id_vereda, int(consentimiento),
                     hoy().isoformat()))
        _guardar_clave(con, pid, clave)
    return pid, clave


def verificar_clave(pid: str, clave: str) -> bool:
    r = uno("SELECT sal, hash_clave FROM credencial WHERE id_paciente = ?", (pid,))
    if r is None:
        _hash(clave, b"0" * 16)          # mismo tiempo de respuesta aunque el código no exista
        return False
    return hmac.compare_digest(_hash(clave, bytes.fromhex(r["sal"])), r["hash_clave"])


def cambiar_clave(pid: str, actual: str, nueva: str) -> bool:
    if not verificar_clave(pid, actual):
        return False
    with conexion() as con:
        _guardar_clave(con, pid, nueva)
    return True


def pacientes(filtro: str = "") -> pd.DataFrame:
    f = f"%{filtro.strip()}%"
    return tabla("""SELECT p.id_paciente, p.nombre, p.fecha_nacimiento, p.sexo,
                           p.grupo_sanguineo || p.factor_rh AS tipo_sangre, v.nombre AS vereda, h.pais,
                           v.conectividad, p.id_vereda,
                           (SELECT COUNT(*) FROM reporte r WHERE r.id_paciente = p.id_paciente) AS reportes
                    FROM paciente p JOIN vereda v USING (id_vereda) JOIN hospital h USING (id_hospital)
                    WHERE p.nombre LIKE ? OR p.id_paciente LIKE ? OR v.nombre LIKE ?
                    ORDER BY p.id_paciente DESC""", (f, f, f))


def paciente(pid: str):
    return uno("""SELECT p.*, v.nombre AS vereda, v.conectividad, v.id_hospital, h.pais
                  FROM paciente p JOIN vereda v USING (id_vereda) JOIN hospital h USING (id_hospital)
                  WHERE id_paciente = ?""", (pid,))


# ---------------- Módulo 2: datos clínicos y envío ----------------
def registrar_reporte(pid, tipo, fecha, motivo, sv: dict, puntaje, prioridad_sug, canal, hay_conexion) -> int:
    pac = paciente(pid)
    with conexion() as con:
        cur = con.execute("""INSERT INTO reporte (id_paciente, id_promotor, tipo_reporte, fecha_reporte, motivo_consulta,
                             requiere_seguimiento, puntaje_alerta, prioridad_sugerida, canal,
                             estado_envio, intentos_envio, fecha_envio, estado_reporte)
                             VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?, 1, ?, ?)""",
                          (pid, promotor_de(pac["id_vereda"]), tipo, fecha.isoformat(), motivo.strip()[:100], puntaje,
                           prioridad_sug, canal,
                           "Enviado" if hay_conexion else "Pendiente",
                           ahora() if hay_conexion else None,
                           "Recibido" if hay_conexion else "Por enviar"))
        rid = cur.lastrowid
        con.execute("""INSERT INTO signos_vitales (id_reporte, talla_cm, peso_kg, fc_lpm, fr_rpm, pas_mmhg, pad_mmhg,
                       spo2_pct, ph_orina) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (rid, sv["talla_cm"], sv["peso_kg"], sv["fc_lpm"], sv["fr_rpm"], sv["pas_mmhg"], sv["pad_mmhg"],
                     sv.get("spo2_pct"), sv.get("ph_orina")))
    return rid


def pendientes_envio() -> pd.DataFrame:
    return tabla("""SELECT r.id_reporte, r.fecha_reporte, p.id_paciente, p.nombre, v.nombre AS vereda, v.conectividad,
                           r.prioridad_sugerida, r.canal, r.intentos_envio
                    FROM reporte r JOIN paciente p USING (id_paciente) JOIN vereda v USING (id_vereda)
                    WHERE r.estado_envio = 'Pendiente' ORDER BY r.fecha_reporte""")


def reintentar_envio(rid: int, hay_conexion: bool) -> None:
    """Paso 4: cada intento suma; si hay conexión el reporte pasa al hospital."""
    with conexion() as con:
        if hay_conexion:
            con.execute("""UPDATE reporte SET intentos_envio = intentos_envio + 1, estado_envio = 'Enviado',
                           fecha_envio = ?, estado_reporte = 'Recibido' WHERE id_reporte = ?""", (ahora(), rid))
        else:
            con.execute("UPDATE reporte SET intentos_envio = intentos_envio + 1 WHERE id_reporte = ?", (rid,))


# ---------------- Módulo 3: bandeja y observación médica ----------------
def bandeja() -> pd.DataFrame:
    return tabla("SELECT * FROM v_bandeja_hospital")


def detalle_reporte(rid: int):
    return uno("""SELECT r.*, s.*, p.nombre, p.fecha_nacimiento, p.sexo, p.grupo_sanguineo || p.factor_rh AS tipo_sangre,
                         v.nombre AS vereda, v.conectividad, v.distancia_km, v.id_hospital, h.pais, h.nombre AS hospital
                  FROM reporte r JOIN signos_vitales s USING (id_reporte) JOIN paciente p USING (id_paciente)
                  JOIN vereda v USING (id_vereda) JOIN hospital h USING (id_hospital)
                  WHERE r.id_reporte = ?""", (rid,))


def marcar_en_revision(rid: int) -> None:
    with conexion() as con:
        con.execute("UPDATE reporte SET estado_reporte = 'En revisión' WHERE id_reporte = ? AND estado_reporte = 'Recibido'",
                    (rid,))


def registrar_atencion(rid, id_profesional, prioridad_asig, seguimiento, cie10, conducta, observacion, medio) -> None:
    """Pasos 6 y 7 en una sola transacción: observación, notificación y cierre del reporte."""
    t = ahora()
    with conexion() as con:
        con.execute("""UPDATE reporte SET prioridad_asignada = ?, requiere_seguimiento = ?, codigo_cie10 = ?,
                       estado_reporte = 'Atendido' WHERE id_reporte = ?""",
                    (prioridad_asig, int(seguimiento), cie10 if seguimiento else None, rid))
        con.execute("""INSERT INTO observacion_medica (id_reporte, id_profesional, fecha_hora, conducta, observacion)
                       VALUES (?, ?, ?, ?, ?)""", (rid, id_profesional, t, conducta, observacion.strip()))
        con.execute("INSERT INTO notificacion (id_reporte, medio, fecha_hora, entregada) VALUES (?, ?, ?, 1)",
                    (rid, medio, t))


# ---------------- Módulo 4: reportes ----------------
def historial_paciente(pid: str) -> pd.DataFrame:
    return tabla("SELECT * FROM v_reporte_clinico WHERE id_paciente = ? ORDER BY fecha_reporte, id_reporte", (pid,))


def reporte_seguimiento() -> pd.DataFrame:
    return tabla("SELECT * FROM v_reporte_seguimiento ORDER BY fecha_reporte DESC, id_reporte DESC")


def reporte_gerencial() -> pd.DataFrame:
    return tabla("SELECT * FROM v_reporte_gerencial ORDER BY pais, vereda, mes")


def indicadores() -> dict:
    r = uno("""SELECT (SELECT COUNT(*) FROM paciente) AS pacientes,
                      (SELECT COUNT(*) FROM reporte) AS reportes,
                      (SELECT COUNT(*) FROM reporte WHERE estado_envio = 'Pendiente') AS pendientes,
                      (SELECT COUNT(*) FROM reporte WHERE estado_reporte IN ('Recibido', 'En revisión')) AS en_bandeja,
                      (SELECT COUNT(*) FROM reporte WHERE estado_reporte IN ('Recibido', 'En revisión')
                                                     AND prioridad_sugerida = 'Alta') AS alertas""")
    return dict(r)


def respuestas_paciente(pid: str) -> pd.DataFrame:
    """Lo que el paciente puede ver de la respuesta del hospital (paso 7)."""
    return tabla("""SELECT r.id_reporte, r.fecha_reporte, r.motivo_consulta, r.estado_reporte,
                           COALESCE(r.prioridad_asignada, r.prioridad_sugerida) AS prioridad,
                           o.conducta, o.observacion, o.fecha_hora AS fecha_respuesta, n.medio AS notificado_por
                    FROM reporte r
                    LEFT JOIN observacion_medica o ON o.id_reporte = r.id_reporte
                    LEFT JOIN notificacion n ON n.id_reporte = r.id_reporte
                    WHERE r.id_paciente = ?
                    ORDER BY r.fecha_reporte DESC, r.id_reporte DESC""", (pid,))


# ---------------- Modo stand (feria): visitantes que entran por el código QR ----------------
def registrar_visitante(alias: str, edad: int, sexo: str, id_vereda: str):
    """Crea un paciente de demostración con el alias del visitante (nunca su nombre real)."""
    nacimiento = hoy() - timedelta(days=int(edad * 365.25) + 1)
    return registrar_paciente(f"{alias.strip()[:30]} (visitante)", nacimiento, sexo, "O", "+", id_vereda, True)


def estado_visitante(rid: int):
    """Estado del reporte del visitante y, si ya existe, la respuesta del médico."""
    return uno("""SELECT r.id_reporte, r.estado_envio, r.estado_reporte, r.prioridad_sugerida,
                         COALESCE(r.prioridad_asignada, r.prioridad_sugerida) AS prioridad,
                         o.conducta, o.observacion, o.fecha_hora AS fecha_respuesta, n.medio
                  FROM reporte r
                  LEFT JOIN observacion_medica o ON o.id_reporte = r.id_reporte
                  LEFT JOIN notificacion n ON n.id_reporte = r.id_reporte
                  WHERE r.id_reporte = ?""", (rid,))


def ultimos_reportes(n: int = 8) -> pd.DataFrame:
    """Los reportes de visitantes más recientes, para la pantalla en vivo del stand."""
    return tabla("""SELECT r.id_reporte, p.nombre, v.nombre AS vereda, h.pais, r.prioridad_sugerida, r.canal,
                           r.estado_envio, r.estado_reporte, s.pas_mmhg || '/' || s.pad_mmhg AS presion, s.fc_lpm
                    FROM reporte r JOIN paciente p USING (id_paciente) JOIN vereda v USING (id_vereda)
                    JOIN hospital h USING (id_hospital) JOIN signos_vitales s USING (id_reporte)
                    WHERE p.nombre LIKE '%(visitante)'
                    ORDER BY r.id_reporte DESC LIMIT ?""", (n,))


def indicadores_stand() -> dict:
    """Cifras de los visitantes para la pantalla del stand."""
    r = uno("""SELECT COUNT(*) AS reportes,
                      SUM(prioridad_sugerida = 'Alta') AS altas, SUM(prioridad_sugerida = 'Media') AS medias,
                      SUM(prioridad_sugerida = 'Baja') AS bajas, SUM(estado_reporte = 'Atendido') AS atendidos,
                      SUM(estado_envio = 'Pendiente') AS sin_senal
               FROM reporte r JOIN paciente p USING (id_paciente) WHERE p.nombre LIKE '%(visitante)'""")
    return {k: int(r[k] or 0) for k in r.keys()}


def ultimo_id_reporte() -> int:
    return int(uno("SELECT COALESCE(MAX(id_reporte), 0) AS n FROM reporte")["n"])
