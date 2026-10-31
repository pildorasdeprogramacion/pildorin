"""
Oídos de Pildorín: recibe el audio del INMP441 (ESP32 -> TCP) y lo transcribe.
Sin robot (uv run main.py --sin-robot) usa el micrófono del computador, y ahí
también puedes escribir el mensaje en vez de hablar.
"""

import os
import sys
import socket
import types

# faster-whisper importa PyAV al cargar, pero aquí no lo usa: el audio le llega ya
# decodificado (numpy). En Windows 11, el Control inteligente de aplicaciones puede
# bloquear PyAV y ese import tumba el programa; un módulo vacío en su lugar lo evita.
sys.modules.setdefault("av", types.ModuleType("av"))

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

PUERTO = 5005
TASA = 16000   # Whisper trabaja a 16 kHz, igual que el micrófono del robot

# Sin robot (uv run main.py --sin-robot o PILDORIN_SIN_ROBOT=1): micrófono del computador.
SIN_ROBOT = "--sin-robot" in sys.argv or os.getenv("PILDORIN_SIN_ROBOT") == "1"

print("Cargando Whisper (la primera vez se descarga, unos 500 MB)...")
# En CPU: la VRAM queda para el LLM y la voz (OmniVoice).
whisper = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=8)
print("Whisper listo.")


def _transcribir(audio: np.ndarray) -> str:
    segments, _ = whisper.transcribe(audio, language="es", vad_filter=True)
    # separados por espacio: si no, las palabras de dos segmentos quedan pegadas ("adiós" + "amigo")
    return " ".join(s.text.strip() for s in segments)


def escuchar_desde_robot() -> str:
    """Espera una transmisión de audio del robot y devuelve la transcripción."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", PUERTO))
        srv.listen(1)
        srv.settimeout(1)   # accept() por ratos: así Ctrl+C también corta en Windows
        print("\nEsperando que presiones el botón del robot... "
              "(¿sin robot? Ctrl+C y corre: uv run main.py --sin-robot)")
        while True:
            try:
                conn, addr = srv.accept()
                break
            except socket.timeout:
                continue
        print(f"Robot grabando ({addr[0]})...")
        datos = b""
        with conn:
            conn.settimeout(30)   # el firmware corta a los 20 s; esto es por si se cae a mitad
            try:
                while chunk := conn.recv(4096):
                    datos += chunk
            except socket.timeout:
                pass

    if len(datos) < 16000:
        return ""
    datos = datos[: len(datos) // 2 * 2]   # muestras de 16 bit completas
    audio = np.frombuffer(datos, dtype=np.int16).astype(np.float32) / 32768.0
    return _transcribir(audio)


def _abrir_microfono(guardar):
    """Abre el micrófono a 16 kHz; si no lo acepta, a su tasa propia (luego se convierte)."""
    try:
        return sd.InputStream(samplerate=TASA, channels=1, dtype="float32", callback=guardar), TASA
    except sd.PortAudioError:
        tasa = int(sd.query_devices(kind="input")["default_samplerate"])
        return sd.InputStream(samplerate=tasa, channels=1, dtype="float32", callback=guardar), tasa


def escuchar_desde_pc() -> str:
    """Micrófono del computador: escribes el mensaje, o das Enter y hablas."""
    texto = input("\nEscribe tu mensaje, o presiona Enter para hablar: ").strip()
    if texto:
        return texto

    bloques = []

    def guardar(indata, frames, tiempo, estado):
        bloques.append(indata[:, 0].copy())

    try:
        grabacion, tasa = _abrir_microfono(guardar)
    except sd.PortAudioError as e:
        print(f"(no pude abrir el micrófono: {e}. Puedes escribir el mensaje.)")
        return ""
    with grabacion:
        input("Grabando... presiona Enter cuando termines.")

    if not bloques:
        return ""
    audio = np.concatenate(bloques)
    if tasa != TASA:
        audio = np.interp(np.arange(0, len(audio), tasa / TASA), np.arange(len(audio)), audio)
        audio = audio.astype(np.float32)
    if len(audio) < TASA // 2:   # menos de medio segundo
        return ""
    print("Transcribiendo...")
    return _transcribir(audio)


def escuchar() -> str:
    """Lo que usa main.py: el micrófono del robot o, con --sin-robot, el del computador."""
    return escuchar_desde_pc() if SIN_ROBOT else escuchar_desde_robot()


if __name__ == "__main__":
    while True:
        print(f"Transcrito: {escuchar()}")
