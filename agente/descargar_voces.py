"""
Baja las voces de Pildorín a la carpeta voces/. Desde la carpeta agente:

    uv run descargar_voces.py

Kokoro (unos 350 MB) es la voz que se usa normalmente; Piper (unos 65 MB) queda
de respaldo por si Kokoro no carga. Lo que ya esté completo no se vuelve a bajar.
"""

import sys
from pathlib import Path

import requests

VOCES = Path(__file__).resolve().parent / "voces"

KOKORO = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
PIPER = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/"

ARCHIVOS = [
    KOKORO + "kokoro-v1.0.onnx",
    KOKORO + "voices-v1.0.bin",
    PIPER + "es_MX-claude-high.onnx",
    PIPER + "es_MX-claude-high.onnx.json",
]


def bajar(url: str) -> None:
    destino = VOCES / url.rsplit("/", 1)[-1]
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("Content-Length", 0))
        if destino.exists() and destino.stat().st_size == total:
            print(f"  {destino.name}: ya estaba")
            return
        parcial = destino.with_name(destino.name + ".parcial")
        hecho = 0
        with open(parcial, "wb") as f:
            for bloque in r.iter_content(chunk_size=1 << 20):
                f.write(bloque)
                hecho += len(bloque)
                if total:
                    print(f"\r  {destino.name}: {hecho * 100 // total}% de {total / 1e6:.0f} MB",
                          end="", flush=True)
    parcial.replace(destino)
    print(f"\r  {destino.name}: listo ({hecho / 1e6:.1f} MB)" + " " * 20)


def main() -> int:
    VOCES.mkdir(exist_ok=True)
    print(f"Bajando las voces a {VOCES}")
    fallos = 0
    for url in ARCHIVOS:
        try:
            bajar(url)
        except (requests.RequestException, OSError) as e:
            print(f"\n  no pude bajar {url}\n  ({e})")
            fallos += 1
    if fallos:
        print("Algo no bajó. Revisa la conexión y vuelve a correr el comando "
              "(lo que ya quedó completo no se repite).")
        return 1
    print("Voces listas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
