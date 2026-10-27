"""Prueba del flujo completo en la interfaz, con los tres perfiles.  Ejecutar:  python -m pytest -q"""
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
os.environ["COIL_DB"] = str(Path(tempfile.mkdtemp()) / "prueba.db")   # no toca la base real
sys.path.insert(0, str(RAIZ))

import db  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = str(RAIZ / "app.py")


def entrar(rol: str, usuario: str, clave: str) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.radio[0].set_value(rol)
    at.text_input[0].set_value(usuario)
    at.text_input[1].set_value(clave)
    at.button[0].click().run()
    assert not at.exception, at.exception
    return at


def ir(at: AppTest, pagina: str) -> AppTest:
    at.sidebar.radio[0].set_value(pagina).run()
    assert not at.exception, at.exception
    return at


def textos(at) -> str:
    partes = [e.value for e in at.error] + [e.value for e in at.success] + [e.value for e in at.warning] + [e.value for e in at.info]
    return " | ".join(str(p) for p in partes)


def test_acceso_por_perfil():
    db.crear_base()
    # Clave equivocada
    at = entrar("Paciente", "P-001", "otra")
    assert "incorrectos" in textos(at) and "auth" not in at.session_state
    # La clave de P-001 NO abre el portal de otro paciente
    at = entrar("Paciente", "P-002", "Usuario123!")
    assert "auth" not in at.session_state
    # Cada perfil ve solo sus módulos
    at = entrar("Paciente", "P-001", "Usuario123!")
    assert at.sidebar.radio[0].options == ["Mi portal"]
    at = entrar("Promotor de salud", "promotor", "Promotor123!")
    assert at.sidebar.radio[0].options == ["1. Registro de pacientes", "2. Datos clínicos y envío"]
    at = entrar("Médico", "medico", "Medico123!")
    assert at.sidebar.radio[0].options == ["Inicio", "📺 Pantalla del stand", "3. Bandeja del hospital", "4. Reportes"]


def test_flujo_completo():
    db.crear_base()
    inicio = db.indicadores()

    # ---- Promotor: registra paciente (sin consentimiento se rechaza) ----
    at = ir(entrar("Promotor de salud", "promotor", "Promotor123!"), "1. Registro de pacientes")
    nombre = [t for t in at.text_input if t.label == "Nombre completo *"][0]
    nombre.set_value("Paciente De Prueba")
    [b for b in at.button if b.label == "Registrar paciente"][0].click().run()
    assert "consentimiento" in textos(at)
    [t for t in at.text_input if t.label == "Nombre completo *"][0].set_value("Paciente De Prueba")
    [c for c in at.checkbox if "consentimiento" in c.label][0].check()
    [b for b in at.button if b.label == "Registrar paciente"][0].click().run()
    msg = textos(at)
    assert "P-038" in msg and "Salud-" in msg, msg
    clave = "Salud-" + msg.split("**Salud-")[1][:6]

    # ---- Promotor: datos inválidos, alerta sincrónica y envío sin señal ----
    at = ir(at, "2. Datos clínicos y envío")
    at.selectbox[0].set_value("P-038")
    at.text_input[0].set_value("Dolor de cabeza")
    nums = at.number_input
    nums[4].set_value(80); nums[5].set_value(90)          # PAS < PAD
    [b for b in at.button if b.label == "Validar y enviar reporte"][0].click().run()
    assert "Datos no válidos" in textos(at)

    at = ir(entrar("Promotor de salud", "promotor", "Promotor123!"), "2. Datos clínicos y envío")
    at.selectbox[0].set_value("P-038")
    at.text_input[0].set_value("Dolor de cabeza y mareo")
    nums = at.number_input
    nums[2].set_value(115); nums[3].set_value(22); nums[4].set_value(150); nums[5].set_value(98); nums[6].set_value(93)
    at.toggle[0].set_value(True)
    [b for b in at.button if b.label == "Validar y enviar reporte"][0].click().run()
    assert "ALERTA SINCRÓNICA" in textos(at), textos(at)
    rid_alto = db.uno("SELECT MAX(id_reporte) AS n FROM reporte")["n"]

    at = ir(entrar("Promotor de salud", "promotor", "Promotor123!"), "2. Datos clínicos y envío")
    at.selectbox[0].set_value("P-038")
    at.text_input[0].set_value("Control general")
    at.toggle[0].set_value(False)
    [b for b in at.button if b.label == "Validar y enviar reporte"][0].click().run()
    assert "Sin conexión" in textos(at)
    rid_pend = db.uno("SELECT MAX(id_reporte) AS n FROM reporte")["n"]
    at = ir(entrar("Promotor de salud", "promotor", "Promotor123!"), "2. Datos clínicos y envío")
    at.selectbox(key="rid_reenvio").set_value(rid_pend)
    at.button(key="btn_reenvio").click().run()
    r = db.uno("SELECT * FROM reporte WHERE id_reporte = ?", (rid_pend,))
    assert (r["estado_envio"], r["estado_reporte"], r["intentos_envio"]) == ("Enviado", "Recibido", 2)

    # ---- Médico: la alerta aparece y se atiende (CIE-10 obligatorio) ----
    at = ir(entrar("Médico", "medico", "Medico123!"), "3. Bandeja del hospital")
    assert any(f"#{rid_alto}" in str(e.value) for e in at.error)
    at.selectbox(key="rid_bandeja").set_value(rid_alto).run()
    [b for b in at.button if b.label == "Guardar atención y notificar"][0].click().run()
    assert "CIE-10" in textos(at)
    at = ir(entrar("Médico", "medico", "Medico123!"), "3. Bandeja del hospital")
    at.selectbox(key="rid_bandeja").set_value(rid_alto).run()
    at.selectbox(key="cie").set_value("R03.0")
    at.text_area[0].set_value("Teleconsulta inmediata; repetir toma en 24 h.")
    [b for b in at.button if b.label == "Guardar atención y notificar"][0].click().run()
    assert "atendido" in textos(at), textos(at)
    r = db.uno("SELECT * FROM reporte WHERE id_reporte = ?", (rid_alto,))
    assert (r["estado_reporte"], r["prioridad_asignada"], r["codigo_cie10"]) == ("Atendido", "Alta", "R03.0")

    # ---- Médico: reportes cargan ----
    at = ir(entrar("Médico", "medico", "Medico123!"), "4. Reportes")
    at.selectbox(key="rep_pac").set_value("P-038").run()
    assert not at.exception

    # ---- Paciente nuevo entra con SU clave y ve la respuesta del médico ----
    at = entrar("Paciente", "P-038", clave)
    assert at.session_state["auth"]["pid"] == "P-038"
    assert any("Teleconsulta inmediata" in str(e.value) for e in at.success), textos(at)
    assert not any("P-001" in str(m.value) for m in at.markdown)

    fin = db.indicadores()
    assert fin["pacientes"] == inicio["pacientes"] + 1 and fin["reportes"] == inicio["reportes"] + 2


def test_pdf_se_genera():
    db.crear_base()
    src = (RAIZ / "app.py").read_text(encoding="utf-8").split("def pantalla_acceso")[0]
    ns = {}
    exec(src.replace("st.set_page_config(", "(lambda **k: None)(").replace("st.markdown(", "(lambda *a, **k: None)("), ns)
    for df in (db.historial_paciente("P-004"), db.reporte_seguimiento(), db.reporte_gerencial()):
        pdf = ns["crear_pdf"]("Prueba", df)
        assert pdf[:4] == b"%PDF" and len(pdf) > 2000
