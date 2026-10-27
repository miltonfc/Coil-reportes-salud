"""Prototipo · Sistema de reportes de salud vereda → hospital rural.

Proyecto COIL UCompensar (Colombia) – UNICDA (República Dominicana) · Actividad 5
Ejecutar:  streamlit run app.py
"""
from datetime import date
from io import BytesIO
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

import pandas as pd
import streamlit as st

import db
import logica as lg
import stand

st.set_page_config(page_title="Reportes de salud rural · COIL", page_icon="🏥", layout="wide")

# Estilo visual discreto: conserva el formato de Streamlit y mejora contraste/jerarquía.
st.markdown("""<style>
.stApp {background: linear-gradient(135deg, #f5f9fc 0%, #eef5f7 100%);}
[data-testid="stSidebar"] {background: linear-gradient(180deg,#123b50,#176b70);}
[data-testid="stSidebar"] * {color: #ffffff !important;}
.stButton > button, .stDownloadButton > button, [data-testid="stFormSubmitButton"] button {border-radius: 10px; font-weight: 650;}
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] button[kind="primary"] {background: #147d80; border-color: #147d80;}
[data-testid="stMetric"] {background: white; padding: 14px; border-radius: 12px; border: 1px solid #dce8ed; box-shadow: 0 2px 8px #123b500c;}
h1, h2, h3 {color: #123b50;}
[data-testid="stSidebar"] [data-testid="stMetric"] {background: #ffffff1a; border: 1px solid #ffffff33; box-shadow: none;}
[data-testid="stSidebar"] [data-testid="stExpander"] details {border-color: #ffffff55;}
[data-testid="stSidebar"] button {background: #ffffff1a; border-color: #ffffff66;}
</style>""", unsafe_allow_html=True)


ETIQUETAS = {
    "id_reporte": "Reporte", "tipo_reporte": "Tipo", "fecha_reporte": "Fecha", "id_paciente": "Código", "Paciente": "Código",
    "nombre": "Nombre", "sexo": "Sexo", "edad": "Edad", "vereda": "Vereda / paraje", "tipo_sangre": "Sangre",
    "talla_cm": "Talla (cm)", "peso_kg": "Peso (kg)", "imc": "IMC", "fc_lpm": "FC (lpm)", "fr_rpm": "FR (rpm)",
    "pas_mmhg": "PA sist.", "pad_mmhg": "PA diast.", "spo2_pct": "SpO2 (%)", "ph_orina": "pH",
    "puntaje_alerta": "Puntaje", "prioridad_sugerida": "Prioridad sugerida", "prioridad_asignada": "Prioridad asignada",
    "prioridad": "Prioridad", "motivo_consulta": "Motivo", "requiere_seguimiento": "Seguim.", "codigo_cie10": "CIE-10",
    "enfermedad": "Condición", "canal": "Canal", "estado_envio": "Envío", "estado_reporte": "Estado", "conducta": "Conducta",
    "observacion": "Observación médica", "fecha_atencion": "Atendido", "fecha_respuesta": "Respuesta",
    "notificado_por": "Notificado por", "pais": "País", "mes": "Mes", "reportes": "Reportes", "prioridad_alta": "Alta",
    "prioridad_media": "Media", "prioridad_baja": "Baja", "con_seguimiento": "Con seguim.",
    "pendientes_envio": "Sin enviar", "pas_promedio": "PA sist. prom.",
}


def crear_pdf(titulo, df, subtitulo="Documento confidencial · COIL Reportes de Salud"):
    """Construye un PDF tabular con encabezados legibles y anchos según el contenido."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), rightMargin=24, leftMargin=24, topMargin=28, bottomMargin=24,
                            title=titulo, author="Proyecto COIL · Reportes de salud")
    estilos = getSampleStyleSheet()
    encabezado = ParagraphStyle("Encabezado", parent=estilos["Title"], textColor=colors.HexColor("#123b50"), alignment=TA_CENTER, fontSize=17)
    normal = ParagraphStyle("Celda", parent=estilos["BodyText"], fontSize=7, leading=8.6)
    cabecera = ParagraphStyle("Cab", parent=normal, fontName="Helvetica-Bold", textColor=colors.white)
    elementos = [Paragraph(titulo, encabezado), Paragraph(subtitulo, estilos["Italic"]), Spacer(1, 12)]
    if df is None or df.empty:
        elementos.append(Paragraph("No hay reportes disponibles para los filtros seleccionados.", estilos["BodyText"]))
    else:
        texto = df.fillna("—").astype(str)
        datos = [[Paragraph(ETIQUETAS.get(c, str(c).replace("_", " ").capitalize()), cabecera) for c in df.columns]]
        for fila in texto.itertuples(index=False, name=None):
            datos.append([Paragraph(v.replace("&", "&amp;").replace("<", "&lt;"), normal) for v in fila])
        # Ancho de cada columna proporcional a su texto más largo (con mínimo y máximo), ajustado a la página
        largo = [min(max(max(len(w) for w in ETIQUETAS.get(c, c).split()) + 1.5, texto[c].str.len().max(), 5), 48)
                 for c in df.columns]
        disponible = landscape(letter)[0] - 48
        anchos = [disponible * l / sum(largo) for l in largo]
        tabla_pdf = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
        tabla_pdf.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#176b70")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("GRID", (0,0), (-1,-1), .35, colors.HexColor("#cbd9df")),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f0f6f8")]),
            ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 4), ("RIGHTPADDING", (0,0), (-1,-1), 4),
            ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING", (0,0), (-1,-1), 4),
        ]))
        elementos.append(tabla_pdf)
    doc.build(elementos)
    return buffer.getvalue()


def pantalla_acceso():
    stand.logos(60, centrado=True)
    st.markdown("<div style='text-align:center;padding:18px 0 4px'><div style='font-size:52px'>🏥</div></div>", unsafe_allow_html=True)
    st.title("Reportes de salud rural")
    st.caption("Acceso seguro · Pacientes, promotores y equipo médico")
    a, b = st.columns([1, 1])
    with a:
        st.markdown("### Iniciar sesión")
        with st.form("login_form"):
            rol = st.radio("Tipo de acceso", ["Paciente", "Promotor de salud", "Médico"], horizontal=True)
            usuario = st.text_input("Usuario", placeholder="Código de paciente (P-001) o usuario")
            clave = st.text_input("Contraseña", type="password")
            entrar = st.form_submit_button("Ingresar", type="primary", width="stretch")
        if entrar:
            u = usuario.strip()
            if rol == "Paciente" and db.verificar_clave(u.upper(), clave):
                # Cada paciente tiene su propia clave (guardada con hash): un código ajeno no abre otro portal.
                st.session_state["auth"] = {"rol": "usuario", "pid": u.upper()}
                st.rerun()
            elif (rol == "Promotor de salud" and u.lower() == os.getenv("COIL_PROMOTOR_USER", "promotor")
                  and clave == os.getenv("COIL_PROMOTOR_PASSWORD", "Promotor123!")):
                st.session_state["auth"] = {"rol": "promotor", "usuario": u.lower()}
                st.rerun()
            elif (rol == "Médico" and u.lower() == os.getenv("COIL_DOCTOR_USER", "medico")
                  and clave == os.getenv("COIL_DOCTOR_PASSWORD", "Medico123!")):
                st.session_state["auth"] = {"rol": "medico", "usuario": u.lower()}
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos.")
    with b:
        st.markdown("### ¿Qué puede hacer cada perfil?")
        st.info("**Paciente:** con su código y su clave personal diligencia el formulario clínico, ve la respuesta del "
                "equipo de salud y descarga solo sus propios reportes.")
        st.warning("**Promotor de salud (vereda / paraje):** registra pacientes, toma signos vitales y envía los reportes, "
                   "con o sin señal.")
        st.success("**Médico (hospital):** revisa la bandeja y las alertas, registra la atención y descarga reportes en PDF.")
        st.markdown("**¿Visitas el stand?** [Envía tu reporte como paciente de la vereda →](?modo=visitante)")
        st.caption("Acceso de demostración: paciente P-001 / Usuario123! · promotor / Promotor123! · medico / Medico123!. "
                   "Las claves de los demás pacientes están en base/claves_demo.csv. Cambie las contraseñas antes de publicar.")

COLOR_PRIORIDAD = {"Alta": "🔴", "Media": "🟠", "Baja": "🟢"}


def aviso_guardado():
    """Muestra el mensaje que dejó la acción anterior (sobrevive al recargar la página)."""
    msg = st.session_state.pop("aviso", None)
    if msg:
        getattr(st, msg[0])(msg[1])


# ======================================================================
# Autenticación y permisos por rol
# ======================================================================
if st.query_params.get("modo") == "visitante":   # lo que se abre al escanear el QR del stand
    stand.pagina_visitante()
    st.stop()

if "auth" not in st.session_state:
    pantalla_acceso()
    st.stop()

auth = st.session_state["auth"]
rol_actual = auth["rol"]
if rol_actual == "usuario":
    PAGINAS = ["Mi portal"]
elif rol_actual == "promotor":
    PAGINAS = ["1. Registro de pacientes", "2. Datos clínicos y envío"]
else:
    PAGINAS = ["Inicio", "📺 Pantalla del stand", "3. Bandeja del hospital", "4. Reportes"]

# ======================================================================
# Barra lateral
# ======================================================================
with st.sidebar:
    st.title("🏥 Reportes de salud rural")
    st.caption("Proyecto COIL · UCompensar – UNICDA")
    stand.logos(26, centrado=True)
    st.caption("Sesión: " + {"usuario": "Paciente " + auth.get("pid", ""), "promotor": "Promotor de salud",
                             "medico": "Equipo médico"}[rol_actual])
    pagina = st.radio("Módulo", PAGINAS, label_visibility="collapsed")
    st.divider()
    k = db.indicadores() if rol_actual == "medico" else None
    if rol_actual == "medico":
        st.metric("Alertas de prioridad alta en espera", k["alertas"])
        st.metric("Reportes sin enviar (sin señal)", k["pendientes"])
    elif rol_actual == "promotor":
        st.metric("Reportes sin enviar (sin señal)", db.indicadores()["pendientes"])
    if st.button("Cerrar sesión", width="stretch"):
        st.session_state.pop("auth", None)
        st.rerun()
    if rol_actual == "medico":
        with st.expander("Reiniciar datos de prueba"):
            st.caption("Vuelve la base al estado original: 37 pacientes y 50 reportes, con claves nuevas. "
                       "Se pierde lo registrado en las pruebas.")
            if st.checkbox("Sí, quiero reiniciar"):
                if st.button("Reiniciar base"):
                    db.crear_base()
                    st.session_state["aviso"] = ("success", "Base reiniciada con los datos de prueba.")
                    st.rerun()


# ======================================================================
# Portal privado del paciente: formulario + solo sus propios reportes
# ======================================================================
if pagina == "Mi portal":
    pid = auth["pid"]
    p = db.paciente(pid)
    st.title("👤 Mi portal de salud")
    st.caption("Tu información es privada: no tienes acceso a la base de datos ni a registros de otras personas.")
    st.markdown(f"### Hola, {p['nombre']} · Código {pid}")
    st.info("Diligencia el formulario con los datos tomados por el personal de salud. Esta herramienta es académica y no sustituye una valoración médica.")
    edad = lg.edad_en(date.fromisoformat(p["fecha_nacimiento"]), db.hoy())
    with st.form("form_reporte_usuario"):
        tipo = st.selectbox("Tipo de reporte", ["Inicial", "Control"])
        motivo = st.text_input("Motivo de consulta *", max_chars=100)
        st.markdown("**Signos vitales**")
        c = st.columns(4)
        talla = c[0].number_input("Talla (cm) *", 1, 250, 165)
        peso = c[1].number_input("Peso (kg) *", 1.0, 350.0, 65.0, step=0.5)
        fc = c[2].number_input("Frecuencia cardiaca (lpm) *", 1, 250, 75)
        fr = c[3].number_input("Frecuencia respiratoria (rpm) *", 1, 100, 16)
        c = st.columns(4)
        pas = c[0].number_input("Presión sistólica (mmHg) *", 1, 300, 118)
        pad = c[1].number_input("Presión diastólica (mmHg) *", 1, 200, 76)
        spo2 = c[2].number_input("SpO₂ (%)", 0, 100, 97)
        ph = c[3].number_input("pH urinario", 0.0, 14.0, 6.0, step=0.5)
        c = st.columns(2)
        midio_spo2 = c[0].checkbox("Se midió SpO₂", value=True)
        midio_ph = c[1].checkbox("Se midió pH", value=False)
        enviar = st.form_submit_button("Enviar mi reporte", type="primary")
    if enviar:
        sv = dict(talla_cm=talla, peso_kg=peso, fc_lpm=fc, fr_rpm=fr, pas_mmhg=pas, pad_mmhg=pad,
                  spo2_pct=spo2 if midio_spo2 else None, ph_orina=ph if midio_ph else None)
        errores = lg.validar_signos(sv)
        if not motivo.strip(): errores.insert(0, "El motivo de consulta es obligatorio.")
        if errores:
            for e in errores: st.error(e)
        else:
            clases = lg.clasificar(sv, edad)
            puntos, _ = lg.puntaje_alerta(clases, db.puntos_criterio())
            pri = lg.prioridad(puntos); can = lg.canal(pri)
            rid = db.registrar_reporte(pid, tipo, db.hoy(), motivo, sv, puntos, pri, can, True)
            st.success(f"Reporte #{rid} enviado al equipo de salud. Prioridad sugerida: {pri}.")
    st.divider()
    st.subheader("Respuestas del equipo de salud")
    resp = db.respuestas_paciente(pid)
    if resp.empty:
        st.info("Todavía no tienes reportes registrados.")
    else:
        for r in resp.head(3).itertuples():
            if pd.notna(r.conducta):          # NaN = el médico aún no responde
                st.success(f"**Reporte #{r.id_reporte} · {r.fecha_reporte}** · {r.motivo_consulta}\n\n"
                           f"**Conducta:** {r.conducta} · **Prioridad:** {r.prioridad}\n\n"
                           f"**Observación médica:** {r.observacion}\n\n"
                           f"Respuesta del {r.fecha_respuesta.replace('T', ' a las ')} · notificado por {r.notificado_por.lower()}")
            else:
                st.info(f"**Reporte #{r.id_reporte} · {r.fecha_reporte}** · {r.motivo_consulta}\n\n"
                        f"Estado: **{r.estado_reporte}**. El equipo de salud aún no ha respondido.")
        if len(resp) > 3:
            with st.expander(f"Ver todas mis respuestas ({len(resp)})"):
                st.dataframe(resp, hide_index=True, width="stretch", column_config={c: ETIQUETAS.get(c, c) for c in resp.columns})

    st.subheader("Mis signos vitales")
    h = db.historial_paciente(pid)
    if not h.empty:
        if len(h) > 1:
            st.line_chart(h.set_index("fecha_reporte")[["pas_mmhg", "pad_mmhg", "fc_lpm"]])
        vista_h = h.drop(columns=[c for c in ["id_paciente", "nombre", "sexo", "vereda", "tipo_sangre"] if c in h.columns])
        vista_h = vista_h.astype(object).where(vista_h.notna(), "—")
        st.dataframe(vista_h, hide_index=True, width="stretch", column_config={c: ETIQUETAS.get(c, c) for c in vista_h.columns})
        cols_pdf = ["id_reporte", "fecha_reporte", "pas_mmhg", "pad_mmhg", "fc_lpm", "fr_rpm", "spo2_pct", "imc",
                    "prioridad_sugerida", "prioridad_asignada"]
        pdf_df = h[cols_pdf].merge(resp[["id_reporte", "conducta", "observacion"]], on="id_reporte", how="left")
        pdf = crear_pdf(f"Historial de salud · {p['nombre']} ({pid})", pdf_df)
        st.download_button("📄 Descargar mi reporte en PDF", pdf, f"reporte_{pid}.pdf", "application/pdf", type="primary")

    with st.expander("🔑 Cambiar mi contraseña"):
        with st.form("form_clave"):
            actual = st.text_input("Contraseña actual", type="password")
            nueva = st.text_input("Contraseña nueva (mínimo 8 caracteres)", type="password")
            repetir = st.text_input("Repita la contraseña nueva", type="password")
            cambiar = st.form_submit_button("Cambiar contraseña")
        if cambiar:
            if len(nueva) < 8:
                st.error("La contraseña nueva debe tener al menos 8 caracteres.")
            elif nueva != repetir:
                st.error("Las contraseñas nuevas no coinciden.")
            elif not db.cambiar_clave(pid, actual, nueva):
                st.error("La contraseña actual no es correcta.")
            else:
                st.success("Contraseña actualizada.")

# ======================================================================
# Inicio
# ======================================================================
if pagina == "Inicio":
    st.title("Sistema de comunicación de reportes de salud")
    st.write("Simula el proceso entre una **vereda o paraje** y el **hospital rural**: el promotor registra al paciente y sus "
             "signos vitales, el sistema calcula la prioridad y decide el canal, y el equipo de salud revisa y responde.")
    c = st.columns(5)
    c[0].metric("Pacientes", k["pacientes"])
    c[1].metric("Reportes", k["reportes"])
    c[2].metric("En bandeja del hospital", k["en_bandeja"])
    c[3].metric("Alertas altas en espera", k["alertas"])
    c[4].metric("Pendientes de envío", k["pendientes"])

    st.subheader("Cómo funciona")
    a, b = st.columns(2)
    with a:
        st.markdown("""
| Paso | Quién | Qué pasa |
|---|---|---|
| 1 | Promotor | Registra paciente y signos vitales (módulos 1 y 2) |
| 2 | Sistema | Valida rangos y campos obligatorios |
| 3 | Sistema | Calcula puntaje de alerta y prioridad |
| 4 | Sistema | Si no hay señal, guarda y reintenta el envío |
| 5 | Sistema | Alta → **sincrónico** (alerta) · resto → **asincrónico** (cola) |
| 6 | Equipo de salud | Revisa, asigna prioridad y conducta (módulo 3) |
| 7 | Sistema | Notifica al paciente y registra la atención |
""")
    with b:
        st.markdown("**Regla de prioridad** (puntos por variable fuera de rango)")
        st.markdown("- Presión Etapa 2: +2 · Etapa 1 o baja: +1\n- FC fuera de 60–100: +1 · FR fuera de 12–20: +1\n"
                    "- SpO₂ < 95: +1 · < 90: +2 · IMC fuera de rango (adultos): +1\n\n"
                    "**Alta** ≥ 3 puntos · **Media** = 2 · **Baja** ≤ 1")
        st.caption("Criterios de referencia con fines académicos: no constituyen diagnóstico clínico.")

# ======================================================================
# 1. Registro de pacientes
# ======================================================================
elif pagina == "1. Registro de pacientes":
    st.title("1. Registro de pacientes")
    st.caption("Lo hace el promotor de salud en la vereda o paraje. Los campos con * son obligatorios.")
    aviso_guardado()
    ver = db.veredas()
    etiquetas = {r.id_vereda: f"{r.nombre} ({r.tipo_division}, {'Colombia' if r.pais == 'CO' else 'Rep. Dominicana'}) · señal: {r.conectividad}"
                 for r in ver.itertuples()}

    with st.form("form_paciente", clear_on_submit=True):
        st.markdown(f"**Nuevo paciente** · se le asignará el código **{db.siguiente_id_paciente()}**")
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre completo *")
        nacimiento = c2.date_input("Fecha de nacimiento *", value=date(2000, 1, 1), min_value=date(1900, 1, 1),
                                   max_value=db.hoy(), format="DD/MM/YYYY")
        c3, c4, c5 = st.columns(3)
        sexo = c3.selectbox("Sexo *", ["F", "M"])
        grupo = c4.selectbox("Grupo sanguíneo *", ["O", "A", "B", "AB"])
        rh = c5.selectbox("Factor Rh *", ["+", "-"])
        vereda = st.selectbox("Vereda / paraje *", list(etiquetas), format_func=etiquetas.get)
        consentimiento = st.checkbox("El paciente firmó el consentimiento informado para el tratamiento de sus datos de salud *")
        enviar = st.form_submit_button("Registrar paciente", type="primary")

    if enviar:
        errores = []
        if len(nombre.strip()) < 3:
            errores.append("Escriba el nombre completo.")
        if not consentimiento:
            errores.append("Sin consentimiento informado no se pueden guardar datos de salud (Ley 1581 de 2012 / Ley 172-13).")
        if errores:
            for e in errores:
                st.error(e)
        else:
            pid, clave = db.registrar_paciente(nombre, nacimiento, sexo, grupo, rh, vereda, consentimiento)
            st.session_state["aviso"] = ("success", f"Paciente **{pid}** · {nombre.strip()} registrado.\n\n"
                                                    f"Entregue al paciente su clave temporal: **{clave}** "
                                                    "(se muestra una sola vez; el paciente puede cambiarla en su portal). "
                                                    "Ahora puede cargar sus signos vitales en el módulo 2.")
            st.rerun()

    st.subheader("Pacientes registrados")
    filtro = st.text_input("Buscar por nombre, código o vereda", placeholder="Ej.: P-001, María, El Carmen")
    df = db.pacientes(filtro)
    st.dataframe(df.drop(columns=["id_vereda"]), hide_index=True, width="stretch",
                 column_config={"id_paciente": "Código", "nombre": "Nombre", "fecha_nacimiento": "Nacimiento",
                                "sexo": "Sexo", "tipo_sangre": "Sangre", "vereda": "Vereda / paraje", "pais": "País",
                                "conectividad": "Señal", "reportes": "Reportes"})
    st.caption(f"{len(df)} pacientes")

# ======================================================================
# 2. Datos clínicos y envío
# ======================================================================
elif pagina == "2. Datos clínicos y envío":
    st.title("2. Ingreso de datos clínicos y envío del reporte")
    st.caption("El promotor toma los signos vitales; el sistema valida, calcula la prioridad y envía al hospital.")
    aviso_guardado()
    pac = db.pacientes()
    if pac.empty:
        st.info("Primero registre un paciente en el módulo 1.")
        st.stop()
    opciones = {r.id_paciente: f"{r.id_paciente} · {r.nombre} · {r.vereda} (señal: {r.conectividad})" for r in pac.itertuples()}
    pid = st.selectbox("Paciente", list(opciones), format_func=opciones.get)
    p = db.paciente(pid)
    edad = lg.edad_en(date.fromisoformat(p["fecha_nacimiento"]), db.hoy())
    st.caption(f"{edad} años · sexo {p['sexo']} · {p['vereda']} · hospital de referencia: {p['id_hospital']}")

    with st.form("form_reporte"):
        c1, c2 = st.columns([1, 3])
        tipo = c1.selectbox("Tipo de reporte", ["Inicial", "Control"])
        motivo = c2.text_input("Motivo de consulta * (máx. 100 caracteres)", max_chars=100)
        st.markdown("**Signos vitales**")
        c = st.columns(4)
        talla = c[0].number_input("Talla (cm) *", 0, 999, 165)
        peso = c[1].number_input("Peso (kg) *", 0.0, 999.0, 65.0, step=0.5, format="%.1f")
        fc = c[2].number_input("Frecuencia cardiaca (lpm) *", 0, 999, 75)
        fr = c[3].number_input("Frecuencia respiratoria (rpm) *", 0, 999, 16)
        c = st.columns(4)
        pas = c[0].number_input("Presión sistólica (mmHg) *", 0, 999, 118)
        pad = c[1].number_input("Presión diastólica (mmHg) *", 0, 999, 76)
        spo2 = c[2].number_input("SpO₂ (%) · opcional", 0, 999, 97)
        ph = c[3].number_input("pH urinario · opcional", 0.0, 14.0, 6.0, step=0.5, format="%.1f")
        c = st.columns(4)
        midio_spo2 = c[2].checkbox("Se midió SpO₂", value=True)
        midio_ph = c[3].checkbox("Se midió pH (tira reactiva)", value=False)
        st.divider()
        hay_conexion = st.toggle("¿Hay conexión en la vereda en este momento?", value=p["conectividad"] != "Sin señal",
                                 help="Simula la señal. Sin conexión el reporte se guarda en el dispositivo y se envía después.")
        enviar = st.form_submit_button("Validar y enviar reporte", type="primary")

    if enviar:
        sv = dict(talla_cm=talla, peso_kg=peso, fc_lpm=fc, fr_rpm=fr, pas_mmhg=pas, pad_mmhg=pad,
                  spo2_pct=spo2 if midio_spo2 else None, ph_orina=ph if midio_ph else None)
        errores = lg.validar_signos(sv)                                  # Paso 2
        if not motivo.strip():
            errores.insert(0, "El motivo de consulta es obligatorio.")
        if errores:
            st.error("**Paso 2 · Datos no válidos: corrija el registro.**\n\n- " + "\n- ".join(errores))
        else:
            clases = lg.clasificar(sv, edad)                               # Paso 3
            puntos, motivos = lg.puntaje_alerta(clases, db.puntos_criterio())
            pri = lg.prioridad(puntos)
            can = lg.canal(pri)                                            # Paso 5
            rid = db.registrar_reporte(pid, tipo, db.hoy(), motivo, sv, puntos, pri, can, hay_conexion)

            st.success(f"Reporte **#{rid}** guardado.")
            m = st.columns(4)
            m[0].metric("Puntaje de alerta", puntos)
            m[1].metric("Prioridad sugerida", f"{COLOR_PRIORIDAD[pri]} {pri}")
            m[2].metric("Canal", can)
            m[3].metric("IMC", clases["imc"])
            st.write("**Clasificación:** " + " · ".join(f"{k}: {v}" for k, v in clases.items() if k != "imc"))
            if motivos:
                st.write("**Sumaron puntos:** " + ", ".join(motivos))
            if not hay_conexion:                                           # Paso 4
                st.warning("📵 **Sin conexión:** el reporte quedó guardado en el dispositivo (estado: Pendiente). "
                           "Reintente el envío abajo cuando haya señal.")
            elif can == "Sincrónico":
                st.error("🔴 **ALERTA SINCRÓNICA:** el hospital recibe la alerta de inmediato y se abre una teleconsulta en tiempo real.")
            else:
                st.info("📨 **Asincrónico:** el reporte entró a la cola priorizada del hospital (módulo 3).")

    st.subheader("Reportes pendientes de envío")
    pend = db.pendientes_envio()
    if pend.empty:
        st.caption("No hay reportes esperando señal.")
    else:
        st.dataframe(pend, hide_index=True, width="stretch",
                     column_config={"id_reporte": "Reporte", "fecha_reporte": "Fecha", "id_paciente": "Código",
                                    "nombre": "Paciente", "vereda": "Vereda / paraje", "conectividad": "Señal",
                                    "prioridad_sugerida": "Prioridad", "canal": "Canal", "intentos_envio": "Intentos"})
        c1, c2, c3 = st.columns([2, 2, 1])
        rid = c1.selectbox("Reporte a reenviar", pend["id_reporte"].tolist(), format_func=lambda x: f"#{x}", key="rid_reenvio")
        senal = c2.toggle("¿Ya hay señal?", value=True, key="senal_reintento")
        if c3.button("Reintentar envío", key="btn_reenvio"):
            db.reintentar_envio(int(rid), senal)
            st.session_state["aviso"] = (("success", f"Reporte #{rid} enviado al hospital.") if senal else
                                         ("warning", f"Sin señal: el reporte #{rid} sigue guardado. Se sumó un intento."))
            st.rerun()

# ======================================================================
# 3. Bandeja del hospital
# ======================================================================
elif pagina == "3. Bandeja del hospital":
    st.title("3. Bandeja del hospital · revisión y observación médica")
    st.caption("Lo usa el equipo de salud. Primero aparece lo urgente; dentro de cada prioridad, lo más antiguo.")
    aviso_guardado()
    bj = db.bandeja()
    stand.aviso_reportes_nuevos(set(bj["id_reporte"]))
    altas = bj[bj["prioridad_sugerida"] == "Alta"]
    for r in altas.itertuples():
        st.error(f"🔴 **ALERTA · Reporte #{r.id_reporte}** · {r.nombre}, {r.edad} años · {r.vereda} ({r.pais}) · "
                 f"PA {r.presion}, FC {r.fc_lpm}, FR {r.fr_rpm}, SpO₂ {r.spo2_pct} → teleconsulta inmediata")
    if bj.empty:
        st.success("No hay reportes en espera.")
        st.stop()

    vista = bj.copy()
    vista.insert(0, "", vista["prioridad_sugerida"].map(COLOR_PRIORIDAD))
    st.dataframe(vista.drop(columns=["motivo_consulta"]), hide_index=True, width="stretch",
                 column_config={"id_reporte": "Reporte", "pais": "País", "vereda": "Vereda / paraje", "conectividad": "Señal",
                                "prioridad_sugerida": "Prioridad", "canal": "Canal", "estado_reporte": "Estado",
                                "fecha_reporte": "Fecha", "id_paciente": "Código", "nombre": "Paciente", "edad": "Edad",
                                "presion": "PA", "fc_lpm": "FC", "fr_rpm": "FR", "spo2_pct": "SpO₂",
                                "puntaje_alerta": "Puntaje"})

    etiqueta = {r.id_reporte: f"{COLOR_PRIORIDAD[r.prioridad_sugerida]} #{r.id_reporte} · {r.nombre} · {r.estado_reporte}"
                for r in bj.itertuples()}
    rid = st.selectbox("Abrir reporte", list(etiqueta), format_func=etiqueta.get, key="rid_bandeja")
    d = db.detalle_reporte(int(rid))
    edad = lg.edad_en(date.fromisoformat(d["fecha_nacimiento"]), date.fromisoformat(d["fecha_reporte"]))
    sv = {k: d[k] for k in lg.RANGOS}
    clases = lg.clasificar(sv, edad)
    _, motivos = lg.puntaje_alerta(clases, db.puntos_criterio())

    st.subheader(f"Reporte #{rid} · {COLOR_PRIORIDAD[d['prioridad_sugerida']]} Prioridad {d['prioridad_sugerida']}")
    st.write(f"**Motivo de la alerta:** {', '.join(motivos) if motivos else 'sin variables fuera de rango'}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**Signos vitales**")
        st.markdown(f"- Presión: **{d['pas_mmhg']}/{d['pad_mmhg']}** mmHg ({clases['PA']})\n"
                    f"- FC: **{d['fc_lpm']}** lpm ({clases['FC']})\n- FR: **{d['fr_rpm']}** rpm ({clases['FR']})\n"
                    f"- SpO₂: **{d['spo2_pct'] if d['spo2_pct'] is not None else '—'}** % ({clases['SpO2']})")
    with c2:
        st.markdown("**Paciente**")
        st.markdown(f"- {d['nombre']} ({d['id_paciente']})\n- {edad} años · sexo {d['sexo']} · sangre {d['tipo_sangre']}\n"
                    f"- {d['vereda']} ({d['pais']}) · {d['distancia_km']} km · señal {d['conectividad']}")
    with c3:
        st.markdown("**Contexto**")
        st.markdown(f"- Motivo: {d['motivo_consulta']}\n- Talla {d['talla_cm']} cm · peso {d['peso_kg']} kg · IMC {clases['imc']} "
                    f"({clases['IMC']})\n- pH: {d['ph_orina'] if d['ph_orina'] is not None else '—'}\n"
                    f"- Enviado: {d['fecha_envio']} ({d['intentos_envio']} intento/s) · canal {d['canal']}")
    hist = db.historial_paciente(d["id_paciente"])
    hist = hist[hist["id_reporte"] != rid]
    if not hist.empty:
        with st.expander(f"Reportes anteriores del paciente ({len(hist)})"):
            st.dataframe(hist[["id_reporte", "fecha_reporte", "pas_mmhg", "pad_mmhg", "fc_lpm", "fr_rpm", "spo2_pct",
                               "prioridad_sugerida", "prioridad_asignada"]], hide_index=True, width="stretch")

    if d["estado_reporte"] == "Recibido":
        if st.button("Marcar como «En revisión»"):
            db.marcar_en_revision(int(rid))
            st.session_state["aviso"] = ("info", f"Reporte #{rid} en revisión.")
            st.rerun()

    st.markdown("#### Respuesta del equipo de salud")
    prof = db.profesionales(d["id_hospital"])
    dx = db.diagnosticos()
    dx_opc = {r.codigo_cie10: f"{r.codigo_cie10} · {r.descripcion}" for r in dx.itertuples()}
    conductas = ["Sin conducta adicional", "Control en vereda", "Cita en hospital", "Teleconsulta", "Remisión urgente"]
    medios = ["SMS", "Llamada", "WhatsApp", "Visita del promotor"]
    with st.form("form_atencion"):
        c1, c2 = st.columns(2)
        prof_id = c1.selectbox("Profesional *", prof["id_personal"].tolist(),
                               format_func=lambda x: " · ".join(prof.loc[prof.id_personal == x, ["nombre", "rol"]].iloc[0]))
        pri_asig = c2.selectbox("Prioridad asignada *", ["Alta", "Media", "Baja"],
                                index=["Alta", "Media", "Baja"].index(d["prioridad_sugerida"]),
                                help="Por defecto, la sugerida por el sistema. El profesional puede cambiarla.")
        c1, c2 = st.columns([1, 3])
        seguimiento = c1.checkbox("Requiere seguimiento", value=d["puntaje_alerta"] >= 1)
        cie = c2.selectbox("Condición a seguir (CIE-10) · obligatoria si hay seguimiento", [""] + list(dx_opc),
                           format_func=lambda x: dx_opc.get(x, "— seleccione —"), key="cie")
        c1, c2 = st.columns(2)
        conducta = c1.selectbox("Conducta *", conductas,
                                index=3 if d["prioridad_sugerida"] == "Alta" else 2 if d["prioridad_sugerida"] == "Media" else 1)
        medio = c2.selectbox("Notificar al paciente por *", medios,
                             index=medios.index(lg.medio_notificacion(d["conectividad"], d["canal"])))
        obs = st.text_area("Observación médica *", placeholder="Ej.: Repetir toma de presión en reposo en 7 días.")
        guardar = st.form_submit_button("Guardar atención y notificar", type="primary")

    if guardar:
        errores = []
        if seguimiento and not cie:
            errores.append("Si requiere seguimiento, seleccione la condición CIE-10.")
        if not obs.strip():
            errores.append("Escriba la observación médica.")
        if errores:
            for e in errores:
                st.error(e)
        else:
            db.registrar_atencion(int(rid), prof_id, pri_asig, seguimiento, cie or None, conducta, obs, medio)
            st.session_state["aviso"] = ("success", f"Reporte #{rid} atendido. Paciente notificado por {medio.lower()}.")
            st.rerun()

# ======================================================================
# 4. Reportes
# ======================================================================
elif pagina == "4. Reportes":
    st.title("4. Generación de reportes")
    t1, t2, t3 = st.tabs(["Clínico individual", "Seguimiento", "Gerencial (agregado)"])

    with t1:
        st.caption("Para el profesional de salud: evolución de un paciente.")
        pac = db.pacientes()
        opciones = {r.id_paciente: f"{r.id_paciente} · {r.nombre} ({r.reportes} reportes)" for r in pac.itertuples()}
        pid = st.selectbox("Paciente", list(opciones), format_func=opciones.get, key="rep_pac")
        h = db.historial_paciente(pid)
        if h.empty:
            st.info("Este paciente aún no tiene reportes.")
        else:
            u = h.iloc[-1]
            c = st.columns(5)
            c[0].metric("Edad", f"{u.edad} años")
            c[1].metric("Tipo de sangre", u.tipo_sangre)
            c[2].metric("Última PA", f"{u.pas_mmhg}/{u.pad_mmhg}")
            c[3].metric("IMC", u.imc)
            c[4].metric("Prioridad", u.prioridad_asignada or u.prioridad_sugerida)
            if len(h) > 1:
                st.line_chart(h.set_index("fecha_reporte")[["pas_mmhg", "pad_mmhg", "fc_lpm"]])
            st.dataframe(h.drop(columns=["id_paciente", "nombre", "sexo", "vereda", "tipo_sangre"]), hide_index=True,
                         width="stretch")
            st.download_button("📄 Descargar reporte individual en PDF", crear_pdf(f"Reporte clínico · {opciones[pid]}", h),
                               f"reporte_{pid}.pdf", "application/pdf")

    with t2:
        st.caption("Para la gestión del caso: estado, conducta y notificación de cada reporte.")
        s = db.reporte_seguimiento()
        c1, c2 = st.columns(2)
        est = c1.multiselect("Estado", sorted(s["estado_reporte"].unique()), default=sorted(s["estado_reporte"].unique()))
        pri = c2.multiselect("Prioridad sugerida", ["Alta", "Media", "Baja"], default=["Alta", "Media", "Baja"])
        s = s[s["estado_reporte"].isin(est) & s["prioridad_sugerida"].isin(pri)]
        st.dataframe(s, hide_index=True, width="stretch")
        st.download_button("Descargar CSV", s.to_csv(index=False).encode("utf-8-sig"), "reporte_seguimiento.csv", "text/csv")
        st.download_button("📄 Descargar seguimiento en PDF", crear_pdf("Reporte de seguimiento", s), "reporte_seguimiento.pdf", "application/pdf")

    with t3:
        st.caption("Para la dirección: datos agregados por país, vereda y mes, **sin nombres ni códigos** (datos sensibles).")
        g = db.reporte_gerencial()
        tot = g.groupby("pais")[["reportes", "prioridad_alta", "prioridad_media", "prioridad_baja", "con_seguimiento",
                                 "pendientes_envio"]].sum()
        c = st.columns(len(tot) * 2)
        for i, (pais, r) in enumerate(tot.iterrows()):
            nom = "Colombia" if pais == "CO" else "Rep. Dominicana"
            c[i * 2].metric(f"Reportes · {nom}", int(r.reportes))
            c[i * 2 + 1].metric(f"Prioridad alta · {nom}", int(r.prioridad_alta))
        por_vereda = g.groupby("vereda")[["prioridad_alta", "prioridad_media", "prioridad_baja"]].sum()
        por_vereda.columns = ["Alta", "Media", "Baja"]
        st.markdown("**Reportes por vereda / paraje y prioridad**")
        st.bar_chart(por_vereda, color=["#D9534F", "#F0AD4E", "#2A9D8F"])
        st.dataframe(g, hide_index=True, width="stretch")
        st.download_button("Descargar CSV", g.to_csv(index=False).encode("utf-8-sig"), "reporte_gerencial.csv", "text/csv")
        st.download_button("📄 Descargar reporte consolidado en PDF", crear_pdf("Reporte gerencial consolidado", g), "reporte_gerencial.pdf", "application/pdf")
        st.markdown("**Descarga de reportes de pacientes**")
        pac_pdf = db.pacientes()
        seleccion = st.multiselect("Selecciona pacientes para incluir", pac_pdf["id_paciente"].tolist(),
                                   format_func=lambda x: f"{x} · {pac_pdf.loc[pac_pdf.id_paciente == x, 'nombre'].iloc[0]}")
        todos = st.checkbox("Incluir todos los pacientes")
        if st.button("Preparar PDF de pacientes", type="primary"):
            ids = pac_pdf["id_paciente"].tolist() if todos else seleccion
            bloques = []
            for paciente_id in ids:
                hx = db.historial_paciente(paciente_id)
                if not hx.empty:
                    hx.insert(0, "Paciente", paciente_id)
                    bloques.append(hx)
            conjunto = pd.concat(bloques, ignore_index=True) if bloques else pd.DataFrame()
            st.session_state["pdf_conjunto"] = crear_pdf("Reportes clínicos seleccionados", conjunto,
                "Documento confidencial · acceso restringido al personal médico")
            st.session_state["pdf_conjunto_nombre"] = "reportes_pacientes_consolidados.pdf"
        if st.session_state.get("pdf_conjunto"):
            st.download_button("⬇️ Descargar PDF consolidado", st.session_state["pdf_conjunto"],
                               st.session_state["pdf_conjunto_nombre"], "application/pdf")


# ======================================================================
# Pantalla del stand (Semana de la Innovación)
# ======================================================================
if pagina == "📺 Pantalla del stand":
    stand.pantalla_stand()
