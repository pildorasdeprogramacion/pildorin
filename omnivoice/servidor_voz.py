"""
Servidor de voz de Pildorin: OmniVoice residente en GPU, expuesto en localhost.

Vive en la carpeta omnivoice/ del repositorio, con su propio entorno (torch con
CUDA). El agente NO importa torch ni omnivoice: le pide el audio por HTTP. Si este
servidor no esta arriba, voz.py cae solo a Kokoro.

Necesita una GPU NVIDIA. Arrancar antes que el agente, desde esta carpeta:

    uv run servidor_voz.py

Endpoints:
    GET  /salud  -> "ok"
    POST /tts    -> cuerpo JSON {"texto": "...", "velocidad": 1.0}; responde PCM int16 mono,
                    sample rate en la cabecera X-Sample-Rate (24000).

Tags que entiende el modelo dentro del texto:
    [laughter] [sigh] [confirmation-en] [question-en] [question-ah] [question-oh]
    [question-ei] [question-yi] [surprise-ah] [surprise-oh] [surprise-wa]
    [surprise-yo] [dissatisfaction-hnn]
"""

print("Importando torch y omnivoice (tarda la primera vez)...", flush=True)

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import numpy as np
import torch
from omnivoice import OmniVoice, VoiceClonePrompt

# ==================== AJUSTES ====================

RAIZ = Path(__file__).resolve().parent
REF = RAIZ / "refs" / "ENERGIA_M1"      # voz elegida (.wav + .txt): hablante 07508 de OpenSLR 72
VOZ_PT = RAIZ / "pildorin_voz.pt"          # prompt de clonacion ya codificado

HOST = "127.0.0.1"
PUERTO = 5007

NUM_STEP = 32       # 32 = calidad, 16 = mas rapido
SAMPLE_RATE = 24000

# ==================== CARGA ====================

if not torch.cuda.is_available():
    raise SystemExit("torch no ve una GPU NVIDIA. OmniVoice necesita una; sin este servidor "
                     "el agente usa Kokoro (ver README.md).")

print("Cargando OmniVoice...", flush=True)
t0 = time.time()
model = OmniVoice.from_pretrained("k2-fsa/OmniVoice", device_map="cuda:0", dtype=torch.float16)

if VOZ_PT.exists():
    prompt = VoiceClonePrompt.load(str(VOZ_PT))
    print(f"Voz cargada desde {VOZ_PT.name}", flush=True)
else:
    prompt = model.create_voice_clone_prompt(
        ref_audio=str(REF.with_suffix(".wav")),
        ref_text=REF.with_suffix(".txt").read_text(encoding="utf-8").strip(),
    )
    prompt.save(str(VOZ_PT))
    print(f"Voz codificada desde {REF.name}.wav y guardada en {VOZ_PT.name}", flush=True)

# La primera generacion compila kernels: se hace aqui para que no la pague el publico.
model.generate(text="Hola.", voice_clone_prompt=prompt, num_step=NUM_STEP)
print(f"Listo en {time.time() - t0:.1f}s", flush=True)


def sintetizar(texto: str, velocidad: float) -> bytes:
    # OmniVoice fija la duracion ANTES de generar (la estima contando caracteres y
    # escalando por el ritmo de la voz de referencia). velocidad < 1.0 le da mas
    # tiempo a la frase; si el tiempo no alcanza, se pierde el final.
    velocidad = min(1.3, max(0.6, float(velocidad)))
    t = time.time()
    audio = model.generate(
        text=texto, voice_clone_prompt=prompt, num_step=NUM_STEP, speed=velocidad,
        postprocess_output=False,   # conserva el silencio final; si se recorta, el
                                    # firmware se come la ultima silaba al cerrar
    )[0]
    torch.cuda.synchronize()
    s = time.time() - t
    dur = len(audio) / SAMPLE_RATE
    print(f"  {s:.2f}s / {dur:.1f}s audio (RTF {s / dur:.2f}, vel {velocidad:.2f}, "
          f"{len(texto) / dur:.1f} car/s)  {texto[:60]!r}", flush=True)
    audio = np.clip(np.asarray(audio, dtype=np.float32), -1.0, 1.0)
    return (audio * 32767.0).astype(np.int16).tobytes()


# ==================== HTTP ====================

class Manejador(BaseHTTPRequestHandler):
    def log_message(self, *_):      # silencia el log por peticion de http.server
        pass

    def _responder(self, codigo: int, cuerpo: bytes, tipo: str, extra: dict | None = None):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/salud":
            self._responder(200, b"ok", "text/plain")
        else:
            self._responder(404, b"no existe", "text/plain")

    def do_POST(self):
        if self.path != "/tts":
            self._responder(404, b"no existe", "text/plain")
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            pedido = json.loads(self.rfile.read(largo).decode("utf-8"))
            texto = pedido.get("texto", "").strip()
            if not texto:
                self._responder(400, b"texto vacio", "text/plain")
                return
            pcm = sintetizar(texto, pedido.get("velocidad", 1.0))
            self._responder(200, pcm, "application/octet-stream",
                            {"X-Sample-Rate": str(SAMPLE_RATE)})
        except Exception as e:      # el servidor no debe morir por una frase rara
            print(f"  ERROR: {e}", flush=True)
            self._responder(500, str(e).encode("utf-8"), "text/plain")


if __name__ == "__main__":
    print(f"Servidor de voz en http://{HOST}:{PUERTO}  (Ctrl+C para salir)", flush=True)
    try:
        HTTPServer((HOST, PUERTO), Manejador).serve_forever()
    except KeyboardInterrupt:
        print("\nCerrando.")