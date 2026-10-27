"""Pruebas de las reglas del sistema.  Ejecutar:  python -m pytest -q"""
import sqlite3
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
import logica as lg  # noqa: E402

SV_NORMAL = dict(talla_cm=165, peso_kg=60, fc_lpm=75, fr_rpm=16, pas_mmhg=115, pad_mmhg=75, spo2_pct=97, ph_orina=None)


def test_datos_validos_no_tienen_errores():
    assert lg.validar_signos(SV_NORMAL) == []


def test_presion_invertida_es_rechazada():
    sv = dict(SV_NORMAL, pas_mmhg=80, pad_mmhg=90)
    assert any("sistólica debe ser mayor" in e for e in lg.validar_signos(sv))


def test_fuera_de_rango_y_obligatorio():
    errores = lg.validar_signos(dict(SV_NORMAL, talla_cm=20, fc_lpm=None))
    assert any("Talla" in e for e in errores) and any("Frecuencia cardiaca es obligatorio" in e for e in errores)


def test_opcionales_pueden_faltar():
    assert lg.validar_signos(dict(SV_NORMAL, spo2_pct=None, ph_orina=None)) == []


def test_caso_p004_es_alta_y_sincronico():
    # P-004 de la prueba de escritorio: PA 135/102, FC 115, FR 21, SpO2 95, IMC 22,2
    sv = dict(talla_cm=150, peso_kg=50, fc_lpm=115, fr_rpm=21, pas_mmhg=135, pad_mmhg=102, spo2_pct=95)
    c = lg.clasificar(sv, 24)
    pts, _ = lg.puntaje_alerta(c)
    assert (c["PA"], c["FC"], c["FR"], pts) == ("Etapa 2", "Taquicardia", "Taquipnea", 4)
    assert lg.prioridad(pts) == "Alta" and lg.canal("Alta") == "Sincrónico"


def test_menor_de_edad_usa_percentil():
    c = lg.clasificar(dict(SV_NORMAL, peso_kg=95), 16)
    assert c["IMC"] == "Ref. pediátrica (percentil)"
    assert lg.puntaje_alerta(c)[0] == 0


def test_edad():
    assert lg.edad_en(date(2000, 10, 22), date(2026, 10, 21)) == 25
    assert lg.edad_en(date(2000, 10, 21), date(2026, 10, 21)) == 26


def test_medio_notificacion():
    assert lg.medio_notificacion("Sin señal", "Sincrónico") == "Visita del promotor"
    assert lg.medio_notificacion("Buena", "Sincrónico") == "Llamada"


def test_reglas_coinciden_con_los_50_reportes_de_prueba():
    """El puntaje que calcula la app es el mismo que tienen guardado los datos de prueba."""
    con = sqlite3.connect(":memory:")
    con.executescript((RAIZ / "base" / "schema_sqlite.sql").read_text(encoding="utf-8"))
    con.executescript((RAIZ / "base" / "datos_prueba.sql").read_text(encoding="utf-8"))
    puntos = {(v, c): p for v, c, p in con.execute("SELECT variable, categoria, puntos FROM criterio_alerta")}
    filas = con.execute("""SELECT r.puntaje_alerta, r.prioridad_sugerida, r.canal, r.fecha_reporte, p.fecha_nacimiento,
                                  s.talla_cm, s.peso_kg, s.fc_lpm, s.fr_rpm, s.pas_mmhg, s.pad_mmhg, s.spo2_pct
                           FROM reporte r JOIN paciente p USING (id_paciente) JOIN signos_vitales s USING (id_reporte)""").fetchall()
    assert len(filas) == 50
    for pts, pri, can, f_rep, f_nac, *v in filas:
        sv = dict(zip(["talla_cm", "peso_kg", "fc_lpm", "fr_rpm", "pas_mmhg", "pad_mmhg", "spo2_pct"], v))
        edad = lg.edad_en(date.fromisoformat(f_nac), date.fromisoformat(f_rep))
        calc, _ = lg.puntaje_alerta(lg.clasificar(sv, edad), puntos)
        assert calc == pts and lg.prioridad(calc) == pri and lg.canal(pri) == can
