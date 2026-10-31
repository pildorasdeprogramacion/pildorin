"""
Voz de Pildorin.

Cadena de motores (usa el primero que responda):
    1. OmniVoice  -> servidor local opcional en 127.0.0.1:5007 (carpeta omnivoice/ del repo),
                     voz clonada y expresiva. Entiende etiquetas como [laughter] o [sigh].
    2. Kokoro     -> CPU, sin dependencias pesadas. La voz normal del laboratorio.
    3. Piper      -> ultimo recurso.

El firmware espera PCM crudo: 16 bit, mono, 22050 Hz (SAMPLE_RATE_OUT en main.cpp).
OmniVoice y Kokoro generan a 24000 Hz, asi que aqui se remuestrea. El firmware no se toca.

Archivos en voces/ (se bajan con  uv run descargar_voces.py  desde la carpeta agente):
    kokoro-v1.0.onnx, voices-v1.0.bin
    es_MX-claude-high.onnx (+ .onnx.json)

Con --sin-robot (o PILDORIN_SIN_ROBOT=1) todo sale por los parlantes del computador.
"""

import io
import json
import os
import re
import socket
import sys
import urllib.request
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from num2words import num2words

# ==================== AJUSTES ====================

# IP fija del robot (la ROBOT_IP de firmware/src/main.cpp). Si tu red no es la de Windows:
# variable PILDORIN_ROBOT_IP (ver red/README.md).
ROBOT_IP = os.getenv("PILDORIN_ROBOT_IP") or "192.168.137.200"
ROBOT_AUDIO_PORT = 5006
SAMPLE_RATE_ROBOT = 22050          # lo que espera el firmware
ROBOT_TIMEOUT_CONEXION = 4         # segundos: si el robot no contesta, se habla por el PC

# Sin robot (uv run main.py --sin-robot o PILDORIN_SIN_ROBOT=1): todo por los parlantes del PC.
SIN_ROBOT = "--sin-robot" in sys.argv or os.getenv("PILDORIN_SIN_ROBOT") == "1"

OMNIVOICE_URL = "http://127.0.0.1:5007"
OMNIVOICE_TIMEOUT = 20             # segundos por trozo
# OmniVoice fija la duracion del audio ANTES de generarlo. Si la frase no cabe en ese
# tiempo, se pierde el final. Menos de 1.0 = mas tiempo por frase (0.85 = +18 %).
OMNIVOICE_VELOCIDAD = 0.8

# Etiquetas que OmniVoice sabe interpretar. Cualquier otra cosa entre corchetes se borra.
TAGS_VALIDOS = {
    "laughter", "sigh", "confirmation-en", "question-en", "question-ah", "question-oh",
    "question-ei", "question-yi", "surprise-ah", "surprise-oh", "surprise-wa",
    "surprise-yo", "dissatisfaction-hnn",
}

# Kokoro: la voz cuando no hay OmniVoice.
KOKORO_VOZ = "em_alex"            # voz masculina en español (em_santa es la otra)
KOKORO_VELOCIDAD = 0.92

# Normalizacion: el pico de cada trozo se lleva a este nivel (0.0 - 1.0).
PICO_OBJETIVO = 0.99
GANANCIA_MAX = 12.0                # tope, para no amplificar silencios
GANANCIA_EXTRA = 1.8               # limitador suave: 1.0 = apagado, 3.0 = muy fuerte
COLA_SILENCIO_S = 0.5              # silencio al final: protege la ultima silaba

MAX_CARACTERES_POR_TROZO = 200     # se sintetiza y se envia por partes

VOCES = Path(__file__).resolve().parent.parent / "voces"

# ==================== MOTORES ====================

_kokoro = None          # el modelo, una vez cargado; False si no se pudo
_piper = None
_omnivoice_ok = False   # se revisa una sola vez, al final del archivo: en Windows, intentar
                        # contra un puerto cerrado tarda ~2 s y se notaria en cada frase


class SinVoz(RuntimeError):
    """No hay ningun motor de voz: ni OmniVoice, ni Kokoro, ni Piper."""


def omnivoice_disponible() -> bool:
    try:
        with urllib.request.urlopen(f"{OMNIVOICE_URL}/salud", timeout=1.5) as r:
            return r.status == 200
    except OSError:
        return False


def _con_omnivoice(texto: str) -> tuple[np.ndarray, int]:
    req = urllib.request.Request(
        f"{OMNIVOICE_URL}/tts",
        data=json.dumps({"texto": texto, "velocidad": OMNIVOICE_VELOCIDAD}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=OMNIVOICE_TIMEOUT) as r:
        sr = int(r.headers.get("X-Sample-Rate", 24000))
        pcm = r.read()
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0, sr


def _cargar_kokoro():
    global _kokoro
    if _kokoro is not None:
        return _kokoro
    modelo, pack = VOCES / "kokoro-v1.0.onnx", VOCES / "voices-v1.0.bin"
    try:
        if not (modelo.exists() and pack.exists()):
            raise FileNotFoundError(f"faltan archivos de Kokoro en {VOCES}")
        from kokoro_onnx import Kokoro

        print("\nCargando Kokoro...")
        _kokoro = Kokoro(str(modelo), str(pack))
    except Exception as e:
        print(f"(Kokoro no disponible: {e})")
        _kokoro = False
    return _kokoro


def _con_kokoro(texto: str) -> tuple[np.ndarray, int]:
    audio, sr = _cargar_kokoro().create(texto, voice=KOKORO_VOZ, speed=KOKORO_VELOCIDAD, lang="es")
    return np.asarray(audio, dtype=np.float32), sr


def _con_piper(texto: str) -> tuple[np.ndarray, int]:
    global _piper
    if _piper is None:
        from piper import PiperVoice

        voz = VOCES / "es_MX-claude-high.onnx"
        if not voz.exists():
            raise SinVoz(f"falta {voz.name} en la carpeta voces/. "
                         "Bájalas con:  uv run descargar_voces.py")
        print("\nCargando Piper (último recurso)...")
        _piper = PiperVoice.load(str(voz))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        _piper.synthesize_wav(texto, w)
    buf.seek(0)
    with wave.open(buf, "rb") as w:
        sr = w.getframerate()
        pcm = w.readframes(w.getnframes())
    return np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0, sr


def _sintetizar(texto: str) -> tuple[np.ndarray, int]:
    """Devuelve (audio float32 en -1..1, sample_rate) con el primer motor que responda."""
    if _omnivoice_ok:
        try:
            return _con_omnivoice(texto)
        except OSError:
            pass                               # servidor caido: siguen los respaldos
        except Exception as e:
            print(f"(OmniVoice fallo: {e})")

    plano = sin_tags(texto)                    # Kokoro y Piper leerian "[laughter]" en voz alta
    if not plano:
        return np.zeros(1, dtype=np.float32), SAMPLE_RATE_ROBOT
    if _cargar_kokoro():
        return _con_kokoro(plano)
    return _con_piper(plano)


# ==================== TEXTO ====================

_RE_CORCHETES = re.compile(r"\[([^\[\]]*)\]")
_RE_NUMERO = re.compile(r"\d[\d.,]*")


def numeros_a_palabras(texto: str) -> str:
    """Escribe las cifras como se dicen: "2026" -> "dos mil veintiseis".

    OmniVoice fija la duracion del audio ANTES de generarlo, contando caracteres:
    a un digito le da el peso de 3,5 letras. "2026" son 4 digitos (peso 14) pero se
    dice con 18 letras, asi que la frase no cabe en el tiempo reservado y el final se
    pierde. Escribiendo el numero con letras, la cuenta le cuadra.
    Convencion espanola: el punto separa miles y la coma decimales.
    """
    def _rep(m: re.Match) -> str:
        crudo = m.group(0)
        s = crudo.rstrip(".,")                  # punto final de la frase, no del numero
        cola = crudo[len(s):]
        try:
            if "," in s:
                entera, _, decimal = s.partition(",")
                palabras = num2words(int(entera.replace(".", "") or 0), lang="es") + " coma "
                palabras += " ".join(num2words(int(d), lang="es") for d in decimal)
            else:
                palabras = num2words(int(s.replace(".", "")), lang="es")
        except (ValueError, OverflowError, NotImplementedError):
            return crudo                        # algo raro: mejor dejarlo como estaba
        return palabras + cola

    texto = texto.replace("%", " por ciento")
    # Solo numeros "sueltos": v2, MP3 o GPIO4 se quedan como estan.
    return _RE_NUMERO.sub(
        lambda m: m.group(0) if (m.start() and texto[m.start() - 1].isalpha()) else _rep(m),
        texto,
    )


def _lineas_a_frases(texto: str) -> str:
    """Cada salto de linea pasa a ser un punto. Si el LLM responde con una lista, se lee
    con pausas y cada item queda como frase propia, no todo de corrido en un solo trozo."""
    frases = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea[-1] not in ".!?…:;,]":
            linea += "."
        frases.append(linea)
    return " ".join(frases)


def _filtrar_tag(m: re.Match) -> str:
    tag = m.group(1).strip().lower()
    return f"[{tag}]" if tag in TAGS_VALIDOS else " "


def sin_tags(texto: str) -> str:
    return re.sub(r"\s+", " ", _RE_CORCHETES.sub(" ", texto)).strip()


def limpiar(texto: str) -> str:
    """Quita lo que el LLM escribe para leer y no para hablar. Conserva los tags validos."""
    t = texto
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL)              # bloques de codigo
    t = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1", t)      # [texto](url) -> texto
    t = re.sub(r"https?://\S+", " ", t)
    t = _RE_CORCHETES.sub(_filtrar_tag, t)
    t = re.sub(r"[*_`#>|]", " ", t)                                # markdown
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]", " ", t)    # emojis
    t = _lineas_a_frases(t)
    t = re.sub(r"\$\s*(\d[\d.,]*\d|\d)", r"\1 dólares", t)          # $49 -> 49 dólares
    t = numeros_a_palabras(t)
    return re.sub(r"\s+", " ", t).strip()


def trozos(texto: str) -> list[str]:
    """Parte por oraciones y agrupa hasta MAX_CARACTERES_POR_TROZO."""
    salida, actual = [], ""
    for o in re.split(r"(?<=[.!?…])\s+", texto):
        if not o:
            continue
        if len(actual) + len(o) + 1 <= MAX_CARACTERES_POR_TROZO:
            actual = f"{actual} {o}".strip()
        else:
            if actual:
                salida.append(actual)
            actual = o
    if actual:
        salida.append(actual)
    return salida


# ==================== AUDIO ====================

def _remuestrear(audio: np.ndarray, origen: int, destino: int) -> np.ndarray:
    """Interpolacion lineal. Suficiente para voz y sin dependencias extra."""
    if origen == destino or len(audio) < 2:
        return audio
    n_destino = int(round(len(audio) * destino / origen))
    x_viejo = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    x_nuevo = np.linspace(0.0, 1.0, num=n_destino, endpoint=False)
    return np.interp(x_nuevo, x_viejo, audio).astype(np.float32)


def _normalizar(audio: np.ndarray) -> np.ndarray:
    """Lleva el pico a PICO_OBJETIVO y sube el cuerpo de la voz con un limitador
    suave (tanh): dobla los picos en vez de recortarlos en cuadrado."""
    pico = float(np.max(np.abs(audio))) if len(audio) else 0.0
    if pico > 1e-4:
        audio = audio * min(PICO_OBJETIVO / pico, GANANCIA_MAX)
    if GANANCIA_EXTRA > 1.0:
        audio = np.tanh(audio * GANANCIA_EXTRA) / np.tanh(GANANCIA_EXTRA)
    return np.clip(audio, -1.0, 1.0)


# ==================== API PUBLICA ====================

def hablar(texto: str):
    """Reproduce por los parlantes del PC."""
    texto = limpiar(texto)
    if not sin_tags(texto):
        return
    try:
        for parte in trozos(texto):
            audio, sr = _sintetizar(parte)
            sd.play(_normalizar(audio), sr)
            sd.wait()
    except SinVoz as e:
        print(f"(sin voz: {e})")


def hablar_robot(texto: str):
    """Sintetiza y reproduce en el parlante del robot, oracion por oracion.
    Sin robot, o si el robot no contesta, lo dice por los parlantes del PC."""
    if SIN_ROBOT:
        hablar(texto)
        return
    texto = limpiar(texto)
    if not sin_tags(texto):
        return
    try:
        # Una sola conexion para toda la respuesta: el firmware la mantiene abierta
        # y tolera los huecos mientras se sintetiza el siguiente trozo.
        with socket.create_connection((ROBOT_IP, ROBOT_AUDIO_PORT), timeout=ROBOT_TIMEOUT_CONEXION) as s:
            s.settimeout(30)
            for parte in trozos(texto):
                audio, sr = _sintetizar(parte)
                audio = _normalizar(_remuestrear(audio, sr, SAMPLE_RATE_ROBOT))
                s.sendall((audio * 32767.0).astype(np.int16).tobytes())
            # Cola de silencio: si el firmware corta algo al cerrar la conexion,
            # que sea silencio y no la ultima silaba.
            s.sendall(np.zeros(int(COLA_SILENCIO_S * SAMPLE_RATE_ROBOT), dtype=np.int16).tobytes())
    except SinVoz as e:
        print(f"(sin voz: {e})")
    except OSError as e:
        print(f"(robot no disponible: {e}, reproduzco en PC)")
        hablar(texto)


_omnivoice_ok = omnivoice_disponible()
if _omnivoice_ok:
    print("Voz: OmniVoice (servidor local).")
elif (VOCES / "kokoro-v1.0.onnx").exists() and (VOCES / "voices-v1.0.bin").exists():
    print("Voz: Kokoro.")
elif (VOCES / "es_MX-claude-high.onnx").exists():
    print("Voz: Piper.")
else:
    print("Voz: no hay voces en la carpeta voces/. Bájalas desde la carpeta agente con:")
    print("     uv run descargar_voces.py")


if __name__ == "__main__":
    hablar("[surprise-oh] ¡Hola, soy Pildorín! Este mes van 15 ventas por $437, "
           "un 20% más que el mes pasado. [laughter] ¿Te armo el reporte?")