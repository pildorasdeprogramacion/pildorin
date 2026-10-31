"""
Telegram para Pildorín: le escribes (texto o nota de voz) y contesta con texto + nota de voz.
El agente puede mandarte archivos (el PDF del reporte) con la tool enviar_telegram.

    TELEGRAM_TOKEN     token de @BotFather
    TELEGRAM_CHAT_ID   tu chat; a cualquier otro se le ignora

Necesita ffmpeg en el PATH: Telegram exige OGG/Opus para las notas de voz.
"""

import io
import os
import subprocess
import threading
import time
import wave

import numpy as np
import requests

import oidos_robot
import voz

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
CHAT_YO = os.getenv("TELEGRAM_CHAT_ID", "")
API = f"https://api.telegram.org/bot{TOKEN}"
SR = 24000   # todos los motores se llevan a esta tasa antes de codificar


def _api(metodo: str, **kw) -> dict:
    try:
        return requests.post(f"{API}/{metodo}", timeout=60, **kw).json()
    except requests.RequestException as e:
        return {"ok": False, "description": str(e)}


# ---------- salida ----------

def enviar_texto(texto: str) -> bool:
    return _api("sendMessage", data={"chat_id": CHAT_YO, "text": texto}).get("ok", False)


def enviar_archivo(ruta: str, texto: str = "") -> bool:
    with open(ruta, "rb") as f:
        return _api("sendDocument", data={"chat_id": CHAT_YO, "caption": texto},
                    files={"document": (os.path.basename(ruta), f)}).get("ok", False)


def _a_ogg(audio: np.ndarray, sr: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(audio, -1, 1) * 32767.0).astype(np.int16).tobytes())
    p = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-c:a", "libopus", "-b:a", "32k", "-f", "ogg", "pipe:1"],
        input=buf.getvalue(), capture_output=True,
    )
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode(errors="ignore"))
    return p.stdout


def enviar_nota_voz(texto: str) -> bool:
    """Misma voz del robot (OmniVoice con sus [laughter], o los respaldos)."""
    limpio = voz.limpiar(texto)
    if not voz.sin_tags(limpio):
        return False
    partes = []
    for trozo in voz.trozos(limpio):
        audio, sr = voz._sintetizar(trozo)
        partes.append(voz._normalizar(voz._remuestrear(audio, sr, SR)))
    ogg = _a_ogg(np.concatenate(partes), SR)
    return _api("sendVoice", data={"chat_id": CHAT_YO},
                files={"voice": ("pildorin.ogg", ogg, "audio/ogg")}).get("ok", False)


# ---------- entrada ----------

def _transcribir(file_id: str) -> str:
    """Nota de voz que TÚ le mandas: la baja, ffmpeg la pasa a PCM 16 kHz y Whisper la lee.
    Se decodifica con ffmpeg porque PyAV está bloqueado (ver stub en oidos_robot.py)."""
    ruta = _api("getFile", data={"file_id": file_id})["result"]["file_path"]
    oga = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{ruta}", timeout=60).content
    p = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", "pipe:0", "-f", "s16le", "-ac", "1", "-ar", "16000", "pipe:1"],
        input=oga, capture_output=True,
    )
    audio = np.frombuffer(p.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    return oidos_robot._transcribir(audio)   # el mismo Whisper que oye al robot


def _atender(u: dict, responder) -> None:
    """Un update de Telegram: lo transcribe si es voz, se lo pasa al agente y contesta."""
    msg = u.get("message") or {}
    if str(msg.get("chat", {}).get("id", "")) != CHAT_YO:
        return
    por_voz = "voice" in msg
    texto = _transcribir(msg["voice"]["file_id"]) if por_voz else msg.get("text", "")
    if not texto.strip():
        return
    print(f"Tú (telegram, {'voz' if por_voz else 'texto'}): {texto}")
    _api("sendChatAction", data={"chat_id": CHAT_YO, "action": "record_voice" if por_voz else "typing"})
    respuesta = responder(texto)
    print(f"Pildorín (telegram): {respuesta}")
    if por_voz:
        try:
            enviar_nota_voz(respuesta)
        except Exception as e:                      # sin ffmpeg, al menos que llegue el texto
            print(f"[telegram] nota de voz falló: {e}")
            enviar_texto(voz.sin_tags(respuesta))
    else:
        enviar_texto(voz.sin_tags(respuesta))


def _bucle(responder):
    # Descarta lo que quedó encolado mientras el bot estaba apagado: el primer
    # turno del día no puede ser un mensaje de ayer.
    offset = 0
    try:
        r = requests.get(f"{API}/getUpdates", params={"offset": -1}, timeout=15).json()
        if r.get("result"):
            offset = r["result"][-1]["update_id"] + 1
    except requests.RequestException:
        pass
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 30}, timeout=40).json()
        except requests.RequestException as e:
            print(f"[telegram] sin red: {e}")
            time.sleep(5)
            continue
        for u in r.get("result", []):
            offset = u["update_id"] + 1
            try:
                _atender(u, responder)
            except Exception as e:                  # un update malo no puede matar el hilo
                print(f"[telegram] update fallido: {e}")


def iniciar(responder) -> None:
    """responder(texto) -> str. Corre en un hilo daemon: muere con main.py."""
    if not (TOKEN and CHAT_YO):
        print("Telegram: faltan TELEGRAM_TOKEN / TELEGRAM_CHAT_ID, no arranco.")
        return
    threading.Thread(target=_bucle, args=(responder,), daemon=True).start()
    print("Telegram: escuchando.")