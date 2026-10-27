"""Modo stand: el visitante envía su reporte por el QR y ve la respuesta del médico."""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.environ.setdefault("COIL_DB", str(Path(tempfile.mkdtemp()) / "prueba.db"))
sys.path.insert(0, str(RAIZ))

import db  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(RAIZ / "app.py")


def visitante() -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60)
    at.query_params["modo"] = "visitante"
    return at.run()


def test_visitante_alerta_y_respuesta():
    db.crear_base()
    at = visitante()
    assert not at.exception, at.exception
    at.text_input[0].set_value("Colibrí")
    at.slider[0].set_value(130)   # FC
    at.slider[1].set_value(28)    # FR
    at.slider[2].set_value(170)   # PAS
    at.slider[3].set_value(100)   # PAD
    at.button[0].click().run()
    assert not at.exception, at.exception
    v = at.session_state["visita"]
    assert v["prioridad"] == "Alta" and v["canal"] == "Sincrónico"
    # Llega a la bandeja del hospital y a la pantalla del stand
    assert v["rid"] in set(db.bandeja()["id_reporte"])
    assert db.indicadores_stand()["altas"] == 1
    # El médico responde y el visitante lo ve
    medico = db.tabla("SELECT id_personal FROM personal_salud WHERE rol <> 'Promotor'")["id_personal"].iloc[0]
    db.registrar_atencion(v["rid"], medico, "Alta", False, None, "Teleconsulta", "Repetir la toma en reposo.", "SMS")
    at.run()
    assert not at.exception, at.exception
    assert "Repetir la toma" in " ".join(m.value for m in at.markdown)


def test_visitante_sin_senal_y_alias_obligatorio():
    db.crear_base()
    at = visitante()
    at.button[0].click().run()
    assert "alias" in " ".join(e.value for e in at.error)
    at.text_input[0].set_value("Ceiba")
    at.toggle[0].set_value(False)
    at.button[0].click().run()
    rid = at.session_state["visita"]["rid"]
    assert db.estado_visitante(rid)["estado_envio"] == "Pendiente"
    at.button[0].click().run()          # «Volvió la señal: enviar ahora»
    assert db.estado_visitante(rid)["estado_envio"] == "Enviado"


def test_pantalla_stand_y_aviso_bandeja():
    db.crear_base()
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.radio[0].set_value("Médico")
    at.text_input[0].set_value("medico")
    at.text_input[1].set_value("Medico123!")
    at.button[0].click().run()
    at.sidebar.radio[0].set_value("📺 Pantalla del stand").run()
    assert not at.exception, at.exception
    assert any("Escanea" in m.value for m in at.markdown)
    at.sidebar.radio[0].set_value("3. Bandeja del hospital").run()
    assert not at.exception, at.exception
