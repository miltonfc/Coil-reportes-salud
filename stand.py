"""Modo stand (Semana de la Innovación).

- pagina_visitante(): lo que ve el visitante al escanear el código QR (?modo=visitante). Sin inicio de sesión:
  escoge un alias, mueve los signos vitales y envía el reporte. Luego ve en vivo cuándo lo responde el médico.
- pantalla_stand(): pantalla para el televisor del stand (perfil médico). Muestra el QR y los reportes
  que van llegando, actualizándose solos.
- aviso_reportes_nuevos(): avisa en la bandeja del médico cuando llegan reportes nuevos.
"""
import base64
import os
from functools import lru_cache
from html import escape
from pathlib import Path

import segno
import streamlit as st

import db
import logica as lg

COLOR = {"Alta": "#E5484D", "Media": "#F59E0B", "Baja": "#2E9E6B"}
ICONO = {"Alta": "🔴", "Media": "🟠", "Baja": "🟢"}
PAIS = {"CO": "Colombia", "RD": "Rep. Dominicana"}
MOTIVOS = ["Control de rutina", "Dolor de cabeza", "Mareo", "Cansancio", "Dificultad para respirar",
           "Fiebre", "Dolor en el pecho", "Otro"]


# ----------------------------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------------------------
def url_visitante() -> str:
    """Dirección que va dentro del QR. Se puede fijar con la variable COIL_URL_PUBLICA."""
    base = os.getenv("COIL_URL_PUBLICA") or st.session_state.get("url_publica")
    if not base:
        try:
            base = st.context.url or ""
        except Exception:
            base = ""
    base = (base or "http://localhost:8501").split("?")[0].rstrip("/")
    return base + "/?modo=visitante"


def qr_svg(texto: str, escala: int = 9) -> str:
    return segno.make(texto, error="m").svg_inline(scale=escala, dark="#123b50", light="#ffffff", border=2)


IMG = Path(__file__).resolve().parent / "img"


@lru_cache(maxsize=None)
def _img64(nombre: str) -> str:
    return base64.b64encode((IMG / nombre).read_bytes()).decode()


def logos_html(alto: int = 44, fondo: bool = True, centrado: bool = False) -> str:
    """Logos de UCompensar y UNICDA lado a lado (siempre sobre blanco, para que se lean en cualquier fondo)."""
    imgs = "".join(f"<img src='data:image/png;base64,{_img64(n)}' alt='{a}' style='height:{alto}px;width:auto;"
                   f"max-width:46%;object-fit:contain'>" for n, a in (("ucompensar.png", "UCompensar"),
                                                                     ("unicda.png", "UNICDA")))
    caja = "background:white;border-radius:14px;padding:10px 16px;box-shadow:0 2px 10px #123b5014;" if fondo else ""
    return (f"<div style='display:flex;align-items:center;gap:{alto // 2}px;flex-wrap:nowrap;"
            f"justify-content:{'center' if centrado else 'flex-start'};{caja}'>{imgs}</div>")


def logos(alto: int = 44, fondo: bool = True, centrado: bool = False) -> None:
    st.markdown(logos_html(alto, fondo, centrado), unsafe_allow_html=True)


def tarjeta(prioridad: str, titulo: str, cuerpo: str) -> None:
    c = COLOR[prioridad]
    st.markdown(
        f"<div style='border-radius:18px;padding:18px 20px;margin:6px 0 14px;background:{c}14;"
        f"border:2px solid {c}'><div style='font-size:13px;letter-spacing:.08em;text-transform:uppercase;"
        f"color:{c};font-weight:700'>{titulo}</div><div style='font-size:17px;color:#123b50;margin-top:6px'>"
        f"{cuerpo}</div></div>", unsafe_allow_html=True)


# ----------------------------------------------------------------------------------------------
# Página del visitante (celular)
# ----------------------------------------------------------------------------------------------
CSS_CELULAR = """<style>
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"], header, [data-testid="stToolbar"] {display:none !important;}
.block-container {max-width: 560px; padding-top: 1.2rem; padding-bottom: 3rem;}
.stApp {background: linear-gradient(180deg, #eef5f7 0%, #ffffff 60%);}
h1 {font-size: 1.7rem !important;}
[data-testid="stFormSubmitButton"] button {width: 100%; padding: .8rem; font-size: 1.1rem;}
</style>"""


def pagina_visitante() -> None:
    st.markdown(CSS_CELULAR, unsafe_allow_html=True)
    visita = st.session_state.get("visita")
    if visita:
        seguimiento_visitante(visita)
        return

    logos(34, centrado=True)
    st.markdown("<div style='font-size:40px;line-height:1;margin-top:14px'>🏡 ➜ 🏥</div>", unsafe_allow_html=True)
    st.title("Hoy eres un paciente de la vereda")
    st.caption("Proyecto COIL · UCompensar (Colombia) – UNICDA (República Dominicana). "
               "Demostración académica: los valores son inventados y nada de esto es un diagnóstico.")

    ver = db.veredas()
    opc = {r.id_vereda: f"{r.nombre} · {PAIS.get(r.pais, r.pais)} (señal: {r.conectividad.lower()})" for r in ver.itertuples()}
    with st.form("form_visitante"):
        alias = st.text_input("Tu alias *", max_chars=30, placeholder="Ej.: Colibrí, Ceiba, Arepa…",
                              help="No uses tu nombre real: el sistema trabaja sin identificar a nadie.")
        con_senal = [i for i, r in enumerate(ver.itertuples()) if r.conectividad == "Buena"]
        id_vereda = st.selectbox("¿En qué vereda o paraje vives?", list(opc), format_func=opc.get,
                                 index=con_senal[0] if con_senal else 0)
        c = st.columns(2)
        edad = c[0].number_input("Edad", 1, 100, 25)
        sexo = c[1].radio("Sexo", ["F", "M"], horizontal=True)
        motivo = st.selectbox("¿Por qué consultas?", MOTIVOS)

        st.markdown("#### Signos vitales")
        st.caption("Muévelos como quieras: prueba valores normales o muy altos y mira qué prioridad te asigna el sistema.")
        fc = st.slider("❤️ Frecuencia cardiaca (lpm)", 30, 220, 75)
        fr = st.slider("🌬️ Frecuencia respiratoria (rpm)", 5, 60, 16)
        pas = st.slider("🩺 Presión sistólica (la alta, mmHg)", 60, 260, 118)
        pad = st.slider("🩺 Presión diastólica (la baja, mmHg)", 30, 160, 76)
        spo2 = st.slider("🫁 Oxígeno en sangre · SpO₂ (%)", 50, 100, 97)
        c = st.columns(2)
        talla = c[0].number_input("Talla (cm)", 40, 250, 165)
        peso = c[1].number_input("Peso (kg)", 2, 300, 65)

        st.markdown("#### Conexión")
        senal = st.toggle("📶 Hay señal en mi vereda en este momento", value=True,
                          help="Apágalo para ver qué pasa cuando no hay señal: el reporte se guarda y sale después.")
        enviar = st.form_submit_button("Enviar mi reporte al hospital", type="primary")

    if not enviar:
        return
    sv = dict(talla_cm=talla, peso_kg=float(peso), fc_lpm=fc, fr_rpm=fr, pas_mmhg=pas, pad_mmhg=pad,
              spo2_pct=spo2, ph_orina=None)
    errores = lg.validar_signos(sv)
    if not alias.strip():
        errores.insert(0, "Escribe un alias (puede ser inventado).")
    if errores:
        st.error("**El sistema revisó los datos y encontró esto** (paso 2 del diagrama):\n\n- " + "\n- ".join(errores))
        return

    clases = lg.clasificar(sv, int(edad))
    puntos, motivos = lg.puntaje_alerta(clases, db.puntos_criterio())
    pri = lg.prioridad(puntos)
    can = lg.canal(pri)
    pid, _ = db.registrar_visitante(alias, int(edad), sexo, id_vereda)
    rid = db.registrar_reporte(pid, "Inicial", db.hoy(), motivo, sv, puntos, pri, can, senal)
    st.session_state["visita"] = {"rid": rid, "pid": pid, "alias": alias.strip(), "puntos": puntos,
                                  "prioridad": pri, "canal": can, "motivos": motivos}
    st.rerun()


def seguimiento_visitante(v: dict) -> None:
    pri = v["prioridad"]
    logos(30, centrado=True)
    st.markdown(f"<div style='font-size:46px;line-height:1'>{ICONO[pri]}</div>", unsafe_allow_html=True)
    st.title(f"{escape(v['alias'])}, tu reporte es el #{v['rid']}")
    explicacion = {
        "Alta": "Tus signos suman varios puntos de alerta. Va por el <b>canal sincrónico</b>: le llega al médico "
                "como alerta inmediata para una teleconsulta.",
        "Media": "Va por el <b>canal asincrónico</b>, en un lugar alto de la cola del hospital.",
        "Baja": "Va por el <b>canal asincrónico</b>: entra a la cola y el médico lo revisa en orden.",
    }[pri]
    tarjeta(pri, f"Prioridad {pri} · puntaje {v['puntos']}", explicacion)
    if v["motivos"]:
        st.caption("Sumaron puntos: " + ", ".join(v["motivos"]))
    estado_en_vivo(v["rid"])
    st.divider()
    if st.button("Enviar otro reporte", width="stretch"):
        st.session_state.pop("visita", None)
        st.rerun()
    st.caption("Demostración académica · Proyecto COIL UCompensar – UNICDA. No es un diagnóstico médico.")


@st.fragment(run_every=4)
def estado_en_vivo(rid: int) -> None:
    """Se vuelve a consultar cada 4 segundos: el visitante ve llegar la respuesta del médico sin recargar."""
    e = db.estado_visitante(rid)
    if e is None:
        st.warning("Este reporte ya no está en el sistema (se reiniciaron los datos de la demostración).")
        return
    if e["estado_envio"] == "Pendiente":
        st.warning("📵 **Sin señal.** Tu reporte quedó guardado en el dispositivo del promotor. "
                   "Cuando vuelva la señal, sale solo hacia el hospital.")
        if st.button("📶 Volvió la señal: enviar ahora", type="primary", width="stretch"):
            db.reintentar_envio(rid, True)
            st.rerun()
        return
    pasos = ["Enviado", "En el hospital", "Revisando", "Respondido"]
    actual = {"Recibido": 1, "En revisión": 2, "Atendido": 3}[e["estado_reporte"]]
    st.progress((actual + 1) / 4, text=" → ".join(f"**{p}**" if i == actual else p for i, p in enumerate(pasos)))
    if e["estado_reporte"] == "Atendido":
        if not st.session_state.get(f"globos_{rid}"):
            st.balloons()
            st.session_state[f"globos_{rid}"] = True
        tarjeta(e["prioridad"], "Respuesta del médico",
                f"<b>{escape(e['conducta'])}</b><br>{escape(e['observacion'])}"
                f"<div style='font-size:13px;color:#4a6572;margin-top:8px'>Notificado por {escape(e['medio'].lower())} · "
                f"{escape(e['fecha_respuesta'].replace('T', ' a las '))}</div>")
    elif e["estado_reporte"] == "En revisión":
        st.info("👩‍⚕️ El médico está revisando tu reporte en este momento…")
    else:
        st.info("🏥 Tu reporte ya está en la bandeja del hospital. Mira la pantalla del stand: "
                "aquí aparecerá la respuesta del médico.")


# ----------------------------------------------------------------------------------------------
# Pantalla del stand (televisor) · perfil médico
# ----------------------------------------------------------------------------------------------
def pantalla_stand() -> None:
    st.markdown("<style>.block-container{padding-top:1.5rem;max-width:100%}</style>", unsafe_allow_html=True)
    url = url_visitante()
    a, b = st.columns([1, 2.2], gap="large", vertical_alignment="center")
    with a:
        logos(46, centrado=True)
    with b:
        st.markdown("<div style='color:#4a6572;font-size:15px'>Proyecto COIL · UCompensar (Colombia) – "
                    "UNICDA (República Dominicana) · Sistema de reportes de salud vereda → hospital rural</div>",
                    unsafe_allow_html=True)
    izq, der = st.columns([1, 2.2], gap="large")
    with izq:
        st.markdown(
            "<div style='background:white;border-radius:22px;padding:22px;text-align:center;"
            "box-shadow:0 6px 24px #123b5022'><div style='font-size:24px;font-weight:800;color:#123b50'>"
            "Escanea y sé un paciente</div><div style='color:#4a6572;margin:4px 0 10px'>Envía tu reporte al hospital "
            f"desde tu celular</div>{qr_svg(url)}<div style='font-size:12px;color:#7a8f99;word-break:break-all'>"
            f"{escape(url)}</div></div>", unsafe_allow_html=True)
        with st.expander("Cambiar la dirección del QR"):
            nueva = st.text_input("Dirección pública de la aplicación", value=url.split("/?")[0],
                                  help="Normalmente se detecta sola. Ej.: https://coil-reportes.streamlit.app")
            if st.button("Usar esta dirección"):
                st.session_state["url_publica"] = nueva.strip()
                st.rerun()
    with der:
        tablero_en_vivo()


@st.fragment(run_every=3)
def tablero_en_vivo() -> None:
    k = db.indicadores_stand()
    st.markdown("<div style='font-size:34px;font-weight:800;color:#123b50;line-height:1.1'>"
                "Del territorio al hospital · en vivo</div>"
                "<div style='color:#4a6572;margin-bottom:12px'>Cada tarjeta es un reporte enviado por un visitante. "
                "El sistema calcula la prioridad y escoge el canal.</div>", unsafe_allow_html=True)
    m = st.columns(5)
    m[0].metric("👥 Visitantes", k["reportes"])
    m[1].metric("🔴 Alta (alerta)", k["altas"])
    m[2].metric("🟠 Media", k["medias"])
    m[3].metric("🟢 Baja", k["bajas"])
    m[4].metric("✅ Respondidos", k["atendidos"])

    ultimo = db.ultimo_id_reporte()
    visto = st.session_state.get("ultimo_visto")
    if visto is not None and ultimo > visto:
        st.toast("🔔 ¡Llegó un reporte nuevo al hospital!")
    st.session_state["ultimo_visto"] = ultimo

    rec = db.ultimos_reportes(8)
    if rec.empty:
        st.info("Todavía no hay reportes de visitantes. ¡Escanea el código y envía el primero!")
        return
    filas = [rec.iloc[i:i + 2] for i in range(0, len(rec), 2)]
    estado_txt = {"Por enviar": "📵 guardado, esperando señal", "Recibido": "🏥 en la bandeja del hospital",
                  "En revisión": "👩‍⚕️ en revisión", "Atendido": "✅ respondido"}
    for fila in filas:
        cols = st.columns(2)
        for col, r in zip(cols, fila.itertuples()):
            c = COLOR[r.prioridad_sugerida]
            alias = escape(r.nombre.replace(" (visitante)", ""))
            col.markdown(
                f"<div style='border-left:8px solid {c};background:white;border-radius:14px;padding:12px 16px;"
                f"margin-bottom:10px;box-shadow:0 2px 10px #123b5014'>"
                f"<div style='display:flex;justify-content:space-between;gap:8px'><b style='font-size:19px;color:#123b50'>"
                f"#{r.id_reporte} · {alias}</b><span style='color:{c};font-weight:800'>{r.prioridad_sugerida.upper()}"
                f"</span></div><div style='color:#4a6572'>{escape(r.vereda)} · {PAIS.get(r.pais, r.pais)} · PA {r.presion} · "
                f"FC {r.fc_lpm}</div><div style='margin-top:4px'>{r.canal} · {estado_txt[r.estado_reporte]}</div></div>",
                unsafe_allow_html=True)


# ----------------------------------------------------------------------------------------------
# Aviso en la bandeja del médico
# ----------------------------------------------------------------------------------------------
@st.fragment(run_every=5)
def aviso_reportes_nuevos(ids_en_pantalla: set) -> None:
    """Revisa cada 5 s si llegaron reportes. No recarga sola la bandeja para no borrar lo que el médico escribe."""
    bj = db.bandeja()
    nuevos = bj[~bj["id_reporte"].isin(ids_en_pantalla)]
    if nuevos.empty:
        st.caption("🟢 Bandeja al día · se revisa automáticamente cada 5 segundos.")
        return
    altas = int((nuevos["prioridad_sugerida"] == "Alta").sum())
    txt = f"🔔 Llegaron {len(nuevos)} reporte(s) nuevo(s)" + (f", {altas} con ALERTA" if altas else "")
    if st.button(txt + " · Actualizar bandeja", type="primary"):
        st.rerun(scope="app")
