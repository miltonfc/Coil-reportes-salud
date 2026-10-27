"""Reglas del sistema (pasos 2, 3 y 5 del diagrama de flujo).

Funciones puras, sin base de datos ni interfaz, para poder probarlas por separado.
Los umbrales son los de la hoja «Criterios» del Excel; los puntos por categoría
se leen de la tabla criterio_alerta (se pasan como diccionario).
"""
from datetime import date

# ---------- Rangos válidos (diccionario de variables) ----------
RANGOS = {
    "talla_cm": (40, 250, "Talla", "cm"),
    "peso_kg": (2, 300, "Peso", "kg"),
    "fc_lpm": (30, 220, "Frecuencia cardiaca", "lpm"),
    "fr_rpm": (5, 60, "Frecuencia respiratoria", "rpm"),
    "pas_mmhg": (60, 260, "Presión sistólica", "mmHg"),
    "pad_mmhg": (30, 160, "Presión diastólica", "mmHg"),
    "spo2_pct": (50, 100, "SpO₂", "%"),
    "ph_orina": (4.5, 8.5, "pH urinario", ""),
}
OPCIONALES = {"spo2_pct", "ph_orina"}

# ---------- Umbrales de referencia (hoja «Criterios») ----------
MAYORIA_EDAD = 18
IMC_BAJO, IMC_SOBREPESO, IMC_OBESIDAD = 18.5, 25, 30
FC_MIN, FC_MAX = 60, 100
FR_MIN, FR_MAX = 12, 20
SPO2_NORMAL, SPO2_MUY_BAJO = 95, 90
PAS_ELEVADA, PAS_ETAPA1, PAS_ETAPA2 = 120, 130, 140
PAD_ETAPA1, PAD_ETAPA2 = 80, 90
PAS_BAJA, PAD_BAJA = 90, 60
PRIORIDAD_ALTA, PRIORIDAD_MEDIA = 3, 2

PUNTOS_POR_DEFECTO = {
    ("IMC", "Bajo peso"): 1, ("IMC", "Normal"): 0, ("IMC", "Sobrepeso"): 1, ("IMC", "Obesidad"): 1,
    ("IMC", "Ref. pediátrica (percentil)"): 0,
    ("PA", "Normal"): 0, ("PA", "Elevada"): 0, ("PA", "Etapa 1"): 1, ("PA", "Etapa 2"): 2, ("PA", "Baja"): 1,
    ("FC", "Normal"): 0, ("FC", "Bradicardia"): 1, ("FC", "Taquicardia"): 1,
    ("FR", "Normal"): 0, ("FR", "Bradipnea"): 1, ("FR", "Taquipnea"): 1,
    ("SpO2", "Normal"): 0, ("SpO2", "Bajo"): 1, ("SpO2", "Muy bajo"): 2,
}


def edad_en(fecha_nacimiento: date, fecha: date) -> int:
    """Años cumplidos en una fecha."""
    return fecha.year - fecha_nacimiento.year - ((fecha.month, fecha.day) < (fecha_nacimiento.month, fecha_nacimiento.day))


def validar_signos(sv: dict) -> list[str]:
    """Paso 2: devuelve la lista de errores (vacía si los datos son válidos)."""
    errores = []
    for campo, (lo, hi, nombre, unidad) in RANGOS.items():
        v = sv.get(campo)
        if v is None:
            if campo not in OPCIONALES:
                errores.append(f"{nombre} es obligatorio.")
            continue
        if not (lo <= v <= hi):
            errores.append(f"{nombre} fuera de rango ({lo}–{hi} {unidad}).".replace(" )", ")"))
    if sv.get("pas_mmhg") is not None and sv.get("pad_mmhg") is not None and sv["pas_mmhg"] <= sv["pad_mmhg"]:
        errores.append("La presión sistólica debe ser mayor que la diastólica.")
    return errores


def calcular_imc(peso_kg: float, talla_cm: float) -> float:
    return peso_kg / (talla_cm / 100) ** 2


def clasificar(sv: dict, edad: int) -> dict:
    """Clasificación de cada variable (AHA/ACC 2017, OMS, rangos de reposo)."""
    imc = calcular_imc(sv["peso_kg"], sv["talla_cm"])
    if edad < MAYORIA_EDAD:
        c_imc = "Ref. pediátrica (percentil)"
    elif imc < IMC_BAJO:
        c_imc = "Bajo peso"
    elif imc < IMC_SOBREPESO:
        c_imc = "Normal"
    elif imc < IMC_OBESIDAD:
        c_imc = "Sobrepeso"
    else:
        c_imc = "Obesidad"

    pas, pad = sv["pas_mmhg"], sv["pad_mmhg"]
    if pas >= PAS_ETAPA2 or pad >= PAD_ETAPA2:
        c_pa = "Etapa 2"
    elif pas >= PAS_ETAPA1 or pad >= PAD_ETAPA1:
        c_pa = "Etapa 1"
    elif pas >= PAS_ELEVADA:
        c_pa = "Elevada"
    elif pas < PAS_BAJA or pad < PAD_BAJA:
        c_pa = "Baja"
    else:
        c_pa = "Normal"

    fc, fr = sv["fc_lpm"], sv["fr_rpm"]
    c_fc = "Bradicardia" if fc < FC_MIN else "Taquicardia" if fc > FC_MAX else "Normal"
    c_fr = "Bradipnea" if fr < FR_MIN else "Taquipnea" if fr > FR_MAX else "Normal"

    spo2 = sv.get("spo2_pct")
    if spo2 is None:
        c_spo2 = "Normal"  # opcional: si no se midió, no suma
    else:
        c_spo2 = "Normal" if spo2 >= SPO2_NORMAL else "Bajo" if spo2 >= SPO2_MUY_BAJO else "Muy bajo"
    return {"IMC": c_imc, "PA": c_pa, "FC": c_fc, "FR": c_fr, "SpO2": c_spo2, "imc": round(imc, 1)}


def puntaje_alerta(clases: dict, puntos: dict | None = None) -> tuple[int, list[str]]:
    """Paso 3: suma de puntos y lista de variables que sumaron (motivo de la alerta)."""
    puntos = puntos or PUNTOS_POR_DEFECTO
    total, motivos = 0, []
    for var in ("PA", "FC", "FR", "SpO2", "IMC"):
        p = puntos.get((var, clases[var]), 0)
        if p:
            total += p
            motivos.append(f"{var}: {clases[var]} (+{p})")
    return total, motivos


def prioridad(puntaje: int) -> str:
    if puntaje >= PRIORIDAD_ALTA:
        return "Alta"
    if puntaje >= PRIORIDAD_MEDIA:
        return "Media"
    return "Baja"


def canal(prioridad_sugerida: str) -> str:
    """Paso 5: alta = sincrónico (alerta + teleconsulta); el resto = cola asincrónica."""
    return "Sincrónico" if prioridad_sugerida == "Alta" else "Asincrónico"


def medio_notificacion(conectividad: str, canal_reporte: str) -> str:
    """Paso 7: cómo se avisa al paciente según la señal de su vereda."""
    if conectividad == "Sin señal":
        return "Visita del promotor"
    return "Llamada" if canal_reporte == "Sincrónico" else "SMS"
