#!/usr/bin/env python3
"""Visor web local para capturas del lector ELAN 04F3:3212."""

import io
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import gi
from PIL import Image, ImageOps, ImageStat

gi.require_version("Gio", "2.0")
from gi.repository import GLib  # noqa: E402

from fprintd_client import FprintdDevice, FprintdError  # noqa: E402


PUBLIC_CAPTURE = Path("/run/elan3212/latest.pgm")
PORT = 8765
ENROLL_TOTAL = 8
POSITIONS = [
    "centro",
    "ligeramente arriba",
    "ligeramente abajo",
    "ligeramente a la izquierda",
    "ligeramente a la derecha",
    "centro",
    "ligeramente arriba",
    "ligeramente abajo",
]
FINGERS = [
    "right-little-finger",
    "left-little-finger",
    "right-ring-finger",
    "left-ring-finger",
    "right-middle-finger",
    "left-middle-finger",
]

state_lock = threading.Lock()
state = {
    "phase": "connecting",
    "message": "Conectando con fprintd…",
    "capture_id": 0,
    "metrics": None,
    "finger": None,
    "mode": "view",
    "enroll_stage": 0,
    "genuine_ok": 0,
    "genuine_fail": 0,
    "impostor_ok": 0,
    "impostor_fail": 0,
    "false_accepts": 0,
}
device = None
capturing = False
enrolling = False
verify_phase = None


def set_state(**changes):
    with state_lock:
        state.update(changes)


def snapshot():
    with state_lock:
        return dict(state)


def newest_capture():
    return PUBLIC_CAPTURE if PUBLIC_CAPTURE.is_file() else None


def analyze(path):
    image = Image.open(path).convert("L")
    width, height = image.size
    deviation = ImageStat.Stat(image).stddev[0]
    return image, width, height, deviation


def on_enroll_status(result, done):
    global capturing, enrolling
    if enrolling:
        current = snapshot()
        stage = current["enroll_stage"]
        if result == "enroll-stage-passed":
            stage += 1
            if stage >= ENROLL_TOTAL:
                set_state(
                    enroll_stage=stage,
                    phase="processing",
                    message="Última etapa completada. Guardando huella…",
                    capture_id=current["capture_id"] + 1,
                )
            else:
                set_state(
                    enroll_stage=stage,
                    phase="waiting",
                    message=(
                        f"Etapa {stage} de {ENROLL_TOTAL} completada. "
                        f"Siguiente: {POSITIONS[min(stage, len(POSITIONS) - 1)]}."
                    ),
                    capture_id=current["capture_id"] + 1,
                )
        elif result in ("enroll-swipe-too-short", "enroll-retry-scan"):
            set_state(
                phase="waiting",
                message=(
                    f"Etapa {stage + 1} de {ENROLL_TOTAL}: no se detectó el dedo. "
                    "Apóyalo completo y mantenlo quieto."
                ),
            )
        elif result == "enroll-completed":
            enrolling = False
            try:
                device.enroll_stop()
            except FprintdError:
                pass
            set_state(
                mode="enroll_done",
                enroll_stage=ENROLL_TOTAL,
                phase="ok",
                message="Huella registrada correctamente.",
            )
        elif result in ("enroll-failed", "enroll-disconnected"):
            enrolling = False
            try:
                device.enroll_stop()
            except FprintdError:
                pass
            set_state(phase="error", message=f"El registro falló: {result}")
        return

    if not capturing:
        return
    if result == "enroll-stage-passed":
        capturing = False
        try:
            device.enroll_stop()
        except FprintdError:
            pass
        set_state(phase="processing", message="Captura recibida. Procesando…")
        threading.Timer(0.8, finish_capture).start()
    elif result in ("enroll-swipe-too-short", "enroll-retry-scan"):
        set_state(
            phase="waiting",
            message="No se detectó el dedo: apóyalo completo y quieto.",
        )
    elif result == "enroll-completed":
        capturing = False
        try:
            device.enroll_stop()
        except FprintdError:
            pass
        threading.Timer(0.8, finish_capture).start()
    elif result in ("enroll-failed", "enroll-disconnected"):
        capturing = False
        try:
            device.enroll_stop()
        except FprintdError:
            pass
        set_state(phase="error", message=f"El lector falló: {result}")


def on_verify_status(result, done):
    global verify_phase
    if verify_phase is None:
        return

    current = snapshot()
    phase = verify_phase

    if result.startswith("verify-match"):
        verify_phase = None
        try:
            device.verify_stop()
        except FprintdError:
            pass
        if phase == "genuine":
            set_state(
                genuine_ok=current["genuine_ok"] + 1,
                phase="ok",
                message="Huella reconocida correctamente.",
            )
        else:
            set_state(
                false_accepts=current["false_accepts"] + 1,
                phase="error",
                message="ALERTA: otro dedo fue aceptado. No actives la huella.",
            )
    elif result.startswith("verify-no-match"):
        verify_phase = None
        try:
            device.verify_stop()
        except FprintdError:
            pass
        if phase == "impostor":
            set_state(
                impostor_ok=current["impostor_ok"] + 1,
                phase="ok",
                message="Otro dedo rechazado correctamente.",
            )
        else:
            set_state(
                genuine_fail=current["genuine_fail"] + 1,
                phase="insufficient",
                message="La huella no coincidió. Inténtalo de nuevo.",
            )
    elif (result.startswith("verify-retry-scan") or
          result.startswith("verify-swipe-too-short")):
        set_state(
            phase="waiting",
            message="Vuelve a apoyar el dedo, quieto 1–2 segundos.",
        )
    else:
        verify_phase = None
        try:
            device.verify_stop()
        except FprintdError:
            pass
        set_state(phase="error", message=f"Verificación: {result}")


def start_verify(phase):
    global verify_phase
    current = snapshot()
    if current["phase"] in ("waiting", "processing"):
        return False, "Ya hay una operación en curso."
    try:
        if device is None:
            connect()
        verify_phase = phase
        set_state(
            mode="test",
            phase="waiting",
            message=(
                "Dedo registrado: apoya el dedo índice derecho y mantenlo quieto."
                if phase == "genuine"
                else "Otro dedo: apoya un dedo distinto y mantenlo quieto."
            ),
        )
        device.verify_start("right-index-finger")
        return True, "Apoya el dedo ahora."
    except Exception as error:
        verify_phase = None
        set_state(phase="error", message=f"No se pudo verificar: {error}")
        return False, str(error)


def finish_capture():
    path = newest_capture()
    if path is None:
        set_state(phase="error", message="No se encontró ninguna imagen capturada.")
        return
    try:
        _image, width, height, deviation = analyze(path)
        good = width >= 70 and height >= 70 and deviation >= 30
    except Exception as error:
        set_state(phase="error", message=f"No se pudo leer la captura: {error}")
        return
    current = snapshot()
    set_state(
        phase="ok" if good else "insufficient",
        message=(
            "Captura válida: se ven crestas y buena calidad."
            if good
            else "Captura insuficiente: apoya el dedo completo y mantenlo quieto."
        ),
        capture_id=current["capture_id"] + 1,
        metrics={
            "width": width,
            "height": height,
            "contrast": round(deviation, 1),
            "file": path.name,
        },
    )


def connect():
    global device
    try:
        device = FprintdDevice()
        device.on_signal("EnrollStatus", on_enroll_status)
        device.on_signal("VerifyStatus", on_verify_status)
        device.claim()
        enrolled = set(device.enrolled_fingers())
        finger = next((item for item in FINGERS if item not in enrolled), FINGERS[0])
        set_state(
            phase="idle",
            message="Lector listo. Pulsa Capturar y apoya el dedo.",
            finger=finger,
            mode="view",
            enroll_stage=0,
        )
        path = newest_capture()
        if path is not None:
            try:
                _image, width, height, deviation = analyze(path)
                good = width >= 70 and height >= 70 and deviation >= 30
                set_state(
                    phase="ok" if good else "insufficient",
                    message=(
                        "Última captura válida. Puedes repetir para comparar."
                        if good
                        else "La última captura fue insuficiente; apoya el dedo completo y quieto."
                    ),
                    capture_id=1,
                    metrics={
                        "width": width,
                        "height": height,
                        "contrast": round(deviation, 1),
                        "file": path.name,
                    },
                )
            except Exception:
                pass
        print("CLAIM_OK", flush=True)
    except Exception as error:
        set_state(phase="error", message=f"No se pudo tomar el lector: {error}")
        print(f"CLAIM_ERROR {error}", flush=True)


def start_capture():
    global capturing
    current = snapshot()
    if current["mode"] in ("enroll", "enroll_done"):
        return False, "El registro de huella está en curso o terminó."
    if current["phase"] == "connecting":
        return False, "El lector todavía está conectando."
    if current["phase"] == "waiting":
        return True, "Ya está esperando que apoyes el dedo."
    try:
        if device is None:
            connect()
        capturing = True
        set_state(phase="waiting", message="Esperando que apoyes el dedo…")
        device.enroll_start(current["finger"] or FINGERS[0])
        print(f"CAPTURE_START {current['finger']}", flush=True)
        return True, "Apoya el dedo ahora."
    except Exception as error:
        capturing = False
        set_state(phase="error", message=f"No se pudo iniciar la captura: {error}")
        return False, str(error)


def start_enroll():
    global enrolling, capturing
    current = snapshot()
    if current["phase"] == "connecting":
        return False, "El lector todavía está conectando."
    if enrolling:
        return True, "El registro ya está en curso."
    try:
        if device is None:
            connect()
        enrolled = set(device.enrolled_fingers())
        if "right-index-finger" in enrolled:
            device.delete_finger("right-index-finger")
        enrolling = True
        capturing = False
        set_state(
            mode="enroll",
            enroll_stage=0,
            phase="waiting",
            message=(
                f"Etapa 1 de {ENROLL_TOTAL}: apoya el dedo índice derecho "
                f"en el {POSITIONS[0]} y mantenlo quieto 1–2 segundos."
            ),
        )
        device.enroll_start("right-index-finger")
        print("ENROLL_START right-index-finger", flush=True)
        return True, "Apoya el dedo índice derecho."
    except Exception as error:
        enrolling = False
        set_state(
            mode="view",
            phase="error",
            message=f"No se pudo iniciar el registro: {error}",
        )
        return False, str(error)


PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Visor del lector de huellas</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; margin: 0; padding: 28px;
         display: flex; justify-content: center; background: #111; color: #eee; }
  main { width: min(900px, 100%); text-align: center; }
  h1 { font-size: 1.6rem; margin: 0 0 8px; }
  p { margin: 8px 0 18px; opacity: .85; }
  #preview { width: 100%; max-width: 620px; min-height: 280px;
             image-rendering: pixelated; border-radius: 14px;
             background: #000; border: 1px solid #333; }
  button { font-size: 1.25rem; padding: 16px 34px; border-radius: 999px;
           border: 0; background: #3b82f6; color: white; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  #status { margin-top: 18px; font-size: 1.1rem; }
  #metrics { margin-top: 8px; opacity: .75; font-family: monospace; }
  .ok { color: #4ade80; } .bad { color: #f87171; } .wait { color: #fbbf24; }
</style>
</head>
<body>
<main>
  <h1>Visor del lector de huellas</h1>
  <p>Pulsa <b>Capturar ahora</b> y apoya el dedo índice derecho sobre el lector; mantenlo quieto 1–2 segundos.</p>
  <img id="preview" alt="Vista previa de la huella">
  <div><button id="capture">Capturar ahora</button></div>
  <div id="status">Conectando…</div>
  <div id="metrics"></div>
</main>
<script>
const button = document.getElementById('capture');
const status = document.getElementById('status');
const metrics = document.getElementById('metrics');
const preview = document.getElementById('preview');
let lastCapture = -1;

async function refresh() {
  try {
    const response = await fetch('/status');
    const data = await response.json();
    status.textContent = data.message;
    status.className = data.phase === 'ok' ? 'ok' :
      (data.phase === 'error' || data.phase === 'insufficient') ? 'bad' : 'wait';
    button.disabled = data.phase === 'waiting' || data.phase === 'processing';
    if (data.metrics) {
      const m = data.metrics;
      metrics.textContent = `${m.width}×${m.height} · contraste ${m.contrast} · ${m.file}`;
    }
    if (data.capture_id !== lastCapture) {
      lastCapture = data.capture_id;
      preview.src = '/image.png?t=' + Date.now();
    }
  } catch (error) {
    status.textContent = 'Error de conexión con el visor local.';
  }
}

button.addEventListener('click', async () => {
  button.disabled = true;
  await fetch('/capture', {method: 'POST'});
  refresh();
});

refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


ENROLL_PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Registrar huella dactilar</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; margin: 0; padding: 28px;
         display: flex; justify-content: center; background: #111; color: #eee; }
  main { width: min(900px, 100%); text-align: center; }
  h1 { font-size: 1.6rem; margin: 0 0 8px; }
  p { margin: 8px 0 18px; opacity: .85; }
  progress { width: min(620px, 100%); height: 18px; }
  #preview { width: 100%; max-width: 620px; min-height: 280px;
             image-rendering: pixelated; border-radius: 14px;
             background: #000; border: 1px solid #333; }
  button { font-size: 1.25rem; padding: 16px 34px; border-radius: 999px;
           border: 0; background: #3b82f6; color: white; cursor: pointer; }
  button:disabled { opacity: .5; cursor: default; }
  #status { margin-top: 18px; font-size: 1.1rem; }
  #metrics { margin-top: 8px; opacity: .75; font-family: monospace; }
  .ok { color: #4ade80; } .bad { color: #f87171; } .wait { color: #fbbf24; }
  a { color: #93c5fd; }
</style>
</head>
<body>
<main>
  <h1>Registrar huella dactilar</h1>
  <p>Apoya el <b>dedo índice derecho</b> ocho veces, quieto 1–2 segundos. Varía un poco la posición: centro, arriba, abajo, izquierda y derecha.</p>
  <progress id="bar" max="8" value="0"></progress>
  <div id="stage">Etapa 0 de 8</div>
  <img id="preview" alt="Vista previa de la huella">
  <div><button id="enroll">Registrar huella</button></div>
  <div id="status">Conectando…</div>
  <div id="metrics"></div>
  <p><a href="/">Volver al visor</a></p>
</main>
<script>
const button = document.getElementById('enroll');
const status = document.getElementById('status');
const metrics = document.getElementById('metrics');
const preview = document.getElementById('preview');
const bar = document.getElementById('bar');
const stageLabel = document.getElementById('stage');
let lastCapture = -1;

async function refresh() {
  try {
    const response = await fetch('/status');
    const data = await response.json();
    status.textContent = data.message;
    status.className = data.phase === 'ok' ? 'ok' :
      (data.phase === 'error' || data.phase === 'insufficient') ? 'bad' : 'wait';
    bar.value = data.enroll_stage || 0;
    stageLabel.textContent = `Etapa ${data.enroll_stage || 0} de 8`;
    button.disabled = data.mode === 'enroll' || data.phase === 'connecting';
    if (data.mode === 'enroll_done') {
      button.textContent = 'Huella registrada';
      button.disabled = true;
    }
    if (data.metrics) {
      const m = data.metrics;
      metrics.textContent = `${m.width}×${m.height} · contraste ${m.contrast}`;
    }
    if (data.capture_id !== lastCapture) {
      lastCapture = data.capture_id;
      preview.src = '/image.png?t=' + Date.now();
    }
  } catch (error) {
    status.textContent = 'Error de conexión con el visor local.';
  }
}

button.addEventListener('click', async () => {
  button.disabled = true;
  await fetch('/enroll/start', {method: 'POST'});
  refresh();
});

refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


TEST_PAGE = """<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Prueba de huella</title>
<style>
  :root { color-scheme: light dark; }
  body { font-family: system-ui, sans-serif; margin: 0; padding: 28px;
         display: flex; justify-content: center; background: #111; color: #eee; }
  main { width: min(900px, 100%); text-align: center; }
  h1 { font-size: 1.6rem; margin: 0 0 8px; }
  p { margin: 8px 0 18px; opacity: .85; }
  #preview { width: 100%; max-width: 420px; min-height: 220px;
             image-rendering: pixelated; border-radius: 14px;
             background: #000; border: 1px solid #333; }
  button { font-size: 1.05rem; padding: 14px 24px; border-radius: 999px;
           border: 0; background: #3b82f6; color: white; cursor: pointer;
           margin: 4px; }
  button.secondary { background: #6b7280; }
  button:disabled { opacity: .5; cursor: default; }
  #status { margin-top: 18px; font-size: 1.1rem; }
  #counters { margin-top: 10px; font-family: monospace; }
  .ok { color: #4ade80; } .bad { color: #f87171; } .wait { color: #fbbf24; }
  a { color: #93c5fd; }
</style>
</head>
<body>
<main>
  <h1>Prueba de huella</h1>
  <p>Haz 5 intentos con el dedo registrado y 5 con un dedo distinto. Cada intento debe ser una pulsación quieta de 1–2 segundos.</p>
  <img id="preview" alt="Vista previa de la huella">
  <div>
    <button id="genuine">Probar dedo registrado</button>
    <button id="impostor" class="secondary">Probar otro dedo</button>
  </div>
  <div id="status">Listo para probar.</div>
  <div id="counters"></div>
  <p><a href="/enroll">Registrar otra vez</a> · <a href="/">Volver al visor</a></p>
</main>
<script>
const status = document.getElementById('status');
const counters = document.getElementById('counters');
const preview = document.getElementById('preview');
const genuine = document.getElementById('genuine');
const impostor = document.getElementById('impostor');
let lastCapture = -1;

async function refresh() {
  try {
    const d = await (await fetch('/status')).json();
    status.textContent = d.message;
    status.className = d.phase === 'ok' ? 'ok' :
      (d.phase === 'error' || d.phase === 'insufficient') ? 'bad' : 'wait';
    const busy = d.phase === 'waiting' || d.phase === 'processing';
    genuine.disabled = busy;
    impostor.disabled = busy;
    counters.textContent =
      `Correctas: ${d.genuine_ok}/5 · Fallos: ${d.genuine_fail} · ` +
      `Otro dedo rechazado: ${d.impostor_ok}/5 · Falsos positivos: ${d.false_accepts}`;
    if (d.capture_id !== lastCapture) {
      lastCapture = d.capture_id;
      preview.src = '/image.png?t=' + Date.now();
    }
  } catch (error) {
    status.textContent = 'Error de conexión con el visor local.';
  }
}

genuine.addEventListener('click', async () => {
  await fetch('/test/verify?phase=genuine', {method: 'POST'});
  refresh();
});
impostor.addEventListener('click', async () => {
  await fetch('/test/verify?phase=impostor', {method: 'POST'});
  refresh();
});

refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        if self.path == "/":
            payload = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/enroll":
            payload = ENROLL_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/test":
            payload = TEST_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/status":
            payload = json.dumps(snapshot()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/image.png"):
            path = newest_capture()
            if path is None:
                self.send_error(404)
                return
            try:
                image, _w, _h, _d = analyze(path)
                output = io.BytesIO()
                ImageOps.autocontrast(image).save(output, format="PNG")
                payload = output.getvalue()
            except Exception:
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_error(404)

    def do_POST(self):
        if self.path == "/capture":
            ok, message = start_capture()
            payload = json.dumps({"ok": ok, "message": message}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path == "/enroll/start":
            ok, message = start_enroll()
            payload = json.dumps({"ok": ok, "message": message}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/test/verify"):
            query = parse_qs(urlparse(self.path).query)
            phase = query.get("phase", ["genuine"])[0]
            ok, message = start_verify(phase)
            payload = json.dumps({"ok": ok, "message": message}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_error(404)


def main():
    loop = GLib.MainLoop()
    threading.Thread(target=loop.run, daemon=True).start()
    connect()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"http://127.0.0.1:{PORT}/", flush=True)
    try:
        server.serve_forever()
    finally:
        try:
            if device is not None:
                device.release()
        except Exception:
            pass


if __name__ == "__main__":
    main()
