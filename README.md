# Prototipo · Sistema de reportes de salud vereda → hospital rural

> **Versión para el stand de la Semana de la Innovación.** Los visitantes escanean un código QR, envían un reporte
> desde su celular y el médico lo recibe en vivo en el computador del stand. Ver **«Modo stand»** al final.

Proyecto COIL · UCompensar (Colombia) – UNICDA (República Dominicana) · Actividad 5

Aplicación en Python (Streamlit + SQLite) con los cuatro módulos pedidos y acceso por perfil:

| Perfil | Usuario de demostración | Qué ve |
|---|---|---|
| Promotor de salud (vereda / paraje) | `promotor` / `Promotor123!` | 1. Registro de pacientes · 2. Datos clínicos y envío (con o sin señal) |
| Médico (hospital) | `medico` / `Medico123!` | Inicio · 3. Bandeja del hospital · 4. Reportes (PDF y CSV) |
| Paciente | `P-001` / `Usuario123!` | Mi portal: formulario, respuesta del médico, sus reportes en PDF, cambio de clave |

**Cada paciente tiene su propia clave**, guardada con hash (PBKDF2-SHA256 con sal); la base nunca guarda la clave en texto.
P-001 usa la clave fija de la demostración; los demás pacientes de prueba reciben una clave aleatoria que queda anotada
en `base/claves_demo.csv` (solo para poder hacer la demostración). Al registrar un paciente nuevo, el promotor ve su
clave temporal una sola vez y el paciente puede cambiarla en su portal.

## Instalación (una sola vez)

1. Instale **Python 3.10 o superior** desde python.org. En Windows marque la casilla **"Add Python to PATH"**.
2. Descomprima esta carpeta y abra una terminal dentro de ella
   (Windows: en la carpeta, escriba `cmd` en la barra de direcciones y presione Enter).
3. Cree un entorno e instale las librerías:

   ```
   python -m venv .venv
   .venv\Scripts\activate          (Windows)
   source .venv/bin/activate       (Mac / Linux)
   pip install -r requirements.txt
   ```

## Ejecutar

```
streamlit run app.py
```

Se abre el navegador en `http://localhost:8501`. Para detener: `Ctrl + C` en la terminal.
La primera vez se crea sola la base `base/reportes_salud.db` con 37 pacientes y 50 reportes de prueba, y el archivo
`base/claves_demo.csv` con las claves de los pacientes. Para volver al estado inicial: entre como médico → barra lateral →
**Reiniciar datos de prueba** (se generan claves nuevas).

## Guion de prueba (casos para la presentación)

**Como promotor** (`promotor` / `Promotor123!`):
1. **Registrar paciente sin consentimiento** (módulo 1): lo rechaza. Escoja la vereda *El Carmen*, marque el consentimiento
   y se guarda como P-038. **Anote la clave temporal** que aparece (Salud-xxxxxx).
2. **Datos no válidos** (módulo 2): presión sistólica 80 y diastólica 90 → «Datos no válidos» (paso 2 del diagrama).
3. **Alerta sincrónica** (módulo 2): paciente P-038, FC 115, FR 22, PA 150/98, con conexión → puntaje 4, prioridad Alta, «ALERTA SINCRÓNICA».
4. **Sin señal** (módulo 2): apague «¿Hay conexión?» → queda en «Reportes pendientes de envío»; luego **Reintentar envío** con señal.

**Como médico** (`medico` / `Medico123!`):
5. **Atención en el hospital** (módulo 3): la alerta aparece arriba en rojo. Intente guardar sin CIE-10 (lo rechaza),
   seleccione R03.0, escriba la observación y guarde → queda Atendido y se notifica al paciente.
6. **Reportes** (módulo 4): historial con gráfica, seguimiento filtrable, reporte gerencial por país y vereda, descargas en PDF.

**Como paciente**:
7. Entre con `P-002` y la clave `Usuario123!` → **lo rechaza** (la clave de un paciente no abre el portal de otro).
8. Entre con `P-038` y la clave temporal del paso 1 → ve la **respuesta del médico** (conducta y observación),
   descarga su PDF y puede cambiar su clave.

## Pruebas automáticas (opcional)

```
pip install pytest
python -m pytest -q
```

Verifica las reglas de prioridad contra los 50 reportes de prueba, el acceso por perfil (una clave no abre otro portal), el flujo completo con los tres perfiles y la generación de los PDF, más el modo stand (15 pruebas).

## Archivos

- `app.py` – interfaz: inicio de sesión, los 4 módulos, portal del paciente y PDF
- `logica.py` – reglas: validación, clasificación AHA/ACC 2017 y OMS, puntaje, prioridad, canal
- `db.py` – consultas a SQLite y credenciales de pacientes (hash con sal)
- `base/schema_sqlite.sql`, `base/datos_prueba.sql` – modelo y datos de la Actividad 4
- `tests/` – pruebas automáticas

Clasificaciones y prioridades con fines académicos: no constituyen diagnóstico clínico. Datos de identificación simulados.

## Cambiar las contraseñas de promotor y médico

Se configuran con variables de entorno antes de ejecutar (ejemplo en PowerShell):

```powershell
$env:COIL_PROMOTOR_USER="promotor"
$env:COIL_PROMOTOR_PASSWORD="UnaClaveFuerte!"
$env:COIL_DOCTOR_USER="doctor"
$env:COIL_DOCTOR_PASSWORD="OtraClaveFuerte!"
streamlit run app.py
```

**Importante:** es un prototipo académico. Antes de usar información real de salud harían falta cuentas individuales
para el personal, control de sesiones, HTTPS, borrar `claves_demo.csv` y una revisión de privacidad y seguridad.


---

## Modo stand (Semana de la Innovación)

**Qué hace**

| Quién | Dónde | Qué ve |
|---|---|---|
| Visitante | Su celular, escaneando el QR (`/?modo=visitante`) | Escoge un alias, vereda, edad y mueve los signos vitales (cualquier valor). Envía y ve su prioridad, el canal y, en vivo, la respuesta del médico |
| Televisor del stand | Perfil médico → **📺 Pantalla del stand** | El QR grande y las tarjetas de los reportes que van llegando (se actualiza cada 3 s) |
| Médico | Perfil médico → **3. Bandeja del hospital** | Aviso «🔔 Llegaron reportes nuevos» cada 5 s; responde y la respuesta aparece en el celular del visitante |

El visitante no necesita usuario ni clave. Se registra con un **alias** (nunca su nombre real) y queda marcado como
«(visitante)». Si apaga «Hay señal en mi vereda», el reporte queda guardado y luego puede enviarlo con «Volvió la señal».

### Publicarlo en internet gratis (Streamlit Community Cloud) · unos 20 minutos

1. **Cree una cuenta en GitHub** (github.com) si no tiene una.
2. **Cree un repositorio nuevo** (botón *New*), por ejemplo `coil-reportes-salud`, público. Dentro del repositorio:
   *Add file → Upload files* y arrastre **el contenido** de esta carpeta (que `app.py` quede en la raíz, junto a
   `requirements.txt`, `db.py`, `logica.py`, `stand.py` y la carpeta `base`). No suba `reportes_salud.db` ni
   `claves_demo.csv` (el archivo `.gitignore` ya los excluye si usa Git). Pulse *Commit changes*.
3. Entre a **share.streamlit.io** e inicie sesión con su cuenta de GitHub.
4. *Create app → Deploy a public app from GitHub*. Escoja el repositorio, la rama `main` y el archivo `app.py`.
   En *App URL* escriba un nombre corto, por ejemplo `coil-reportes-salud`.
5. En *Advanced settings → Secrets* pegue (cambie las claves por unas suyas):

   ```toml
   COIL_PROMOTOR_PASSWORD = "UnaClaveDelStand!"
   COIL_DOCTOR_PASSWORD = "OtraClaveDelStand!"
   COIL_URL_PUBLICA = "https://coil-reportes-salud.streamlit.app"
   ```

   `COIL_URL_PUBLICA` es la dirección que irá dentro del QR: debe ser igual a la que escogió en el paso 4.
6. Pulse **Deploy**. En 2–3 minutos la aplicación queda en `https://coil-reportes-salud.streamlit.app`.
7. Pruebe: entre como médico → **📺 Pantalla del stand**, escanee el QR con su celular y envíe un reporte.

**Para actualizar** la aplicación basta con subir los archivos cambiados al repositorio: se vuelve a publicar sola.

### El día del stand

- **Abra la aplicación 30 minutos antes.** Si nadie la usa por un tiempo, Streamlit la «duerme»; al abrirla
  aparece un botón para despertarla (tarda un minuto).
- En el perfil médico: barra lateral → **Reiniciar datos de prueba**, para empezar el día con la pantalla limpia.
- **Televisor:** perfil médico → 📺 Pantalla del stand, oculte la barra lateral (««») y ponga pantalla completa (F11).
- **Segundo computador o portátil:** perfil médico → 3. Bandeja del hospital, para responder.
- Los datos viven en el servidor mientras la aplicación esté encendida; si se reinicia, vuelve a los datos de prueba.
  Para una demostración es suficiente. Si quisieran conservarlos, el paso siguiente sería conectar la base de Neon.
- Recuerde a los visitantes que es una demostración académica: los valores son inventados y no es un diagnóstico.

### Plan B sin internet de la universidad (red local)

1. Conecte el computador y los celulares a la **misma red** (por ejemplo, el punto de acceso de un celular; algunas
   redes de universidad no dejan que los equipos se vean entre sí).
2. Ejecute `streamlit run app.py`. En la terminal aparece una línea **Network URL**, por ejemplo
   `http://192.168.1.20:8501`.
3. En la Pantalla del stand, abra **«Cambiar la dirección del QR»**, pegue esa dirección y pulse **Usar esta dirección**.
   El QR ya apunta a su computador. Si Windows pregunta por el firewall, permita el acceso en redes privadas.

Archivos nuevos de esta versión: `stand.py` (modo visitante, pantalla del stand y aviso de la bandeja) y
`tests/test_stand.py` (3 pruebas más: 15 en total).
