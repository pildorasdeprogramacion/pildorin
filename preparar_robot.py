"""
Deja todo listo para trabajar con el robot. Desde la carpeta del repositorio, en
Windows, macOS o Linux:

    uv run preparar_robot.py

1. Red: prende el hotspot (Windows y Linux) o revisa que estés en la red del robot.
2. Mosquitto: lo arranca si está apagado y revisa que el robot lo pueda alcanzar.
3. Modelo: revisa que Ollama esté corriendo con el modelo, o la API key de Bedrock.
4. Robot: revisa que el agente busque al robot en su IP y si ya está en la red.
5. Voz: arranca OmniVoice si lo instalaste; si no, revisa las voces de Kokoro.
   Con  uv run preparar_robot.py --kokoro  no arranca OmniVoice (deja la memoria
   de la tarjeta gráfica para Ollama).

El nombre y la clave de la red y las IP los lee de la sección CONFIG de
firmware/src/main.cpp. Lo que se hace una sola vez (instalar y configurar
Mosquitto, abrir el firewall) está en red/README.md.
"""

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
SISTEMA = platform.system()                       # "Windows", "Darwin" (macOS) o "Linux"
HOTSPOT_IP = {"Windows": "192.168.137.1", "Linux": "10.42.0.1"}   # la IP que da cada hotspot
SECCION_RED = {"Windows": "sección 2", "Darwin": "sección 3", "Linux": "sección 4"}.get(SISTEMA, "")

faltas = []


def ok(texto):
    print(f"  [ok]    {texto}")


def aviso(texto):
    print(f"  [aviso] {texto}")


def falta(texto):
    print(f"  [falta] {texto}")
    faltas.append(texto)


def tengo_ip(ip: str) -> bool:
    """True si este computador tiene esa IP en alguna de sus redes."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.bind((ip, 0))
        return True
    except OSError:
        return False


def puerto_abierto(ip: str, puerto: int) -> bool:
    try:
        with socket.create_connection((ip, puerto), timeout=1):
            return True
    except OSError:
        return False


def pedir(url: str):
    try:
        with urllib.request.urlopen(url, timeout=2) as r:
            return r.read()
    except OSError:
        return None


def correr(comando: list[str]) -> None:
    """Corre un comando del sistema mostrando su salida; si no existe, lo dice."""
    try:
        subprocess.run(comando)
    except FileNotFoundError:
        aviso(f"no encontré el comando {comando[0]}")


def leer_firmware() -> dict:
    """WIFI_SSID, WIFI_PASS, PC_IP y ROBOT_IP de la sección CONFIG de main.cpp."""
    cpp = (RAIZ / "firmware" / "src" / "main.cpp").read_text(encoding="utf-8")
    datos = {}
    for nombre in ("WIFI_SSID", "WIFI_PASS"):
        m = re.search(rf'{nombre}\s*=\s*"([^"]*)"', cpp)
        datos[nombre] = m.group(1) if m else None
    for nombre in ("PC_IP", "ROBOT_IP"):
        m = re.search(rf"IPAddress\s+{nombre}\((\d+),\s*(\d+),\s*(\d+),\s*(\d+)\)", cpp)
        datos[nombre] = ".".join(m.groups()) if m else None
    if None in datos.values():
        raise SystemExit("No pude leer WIFI_SSID, WIFI_PASS, PC_IP y ROBOT_IP en firmware/src/main.cpp.")
    return datos


def leer_env() -> dict:
    """Las variables de agente/.env, si existe: así se revisa lo mismo que verá el agente."""
    ruta = RAIZ / "agente" / ".env"
    if not ruta.exists():
        return {}
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    pares = [l.split("=", 1) for l in lineas if "=" in l and not l.lstrip().startswith("#")]
    return {k.strip(): v.strip() for k, v in pares}


def variable(nombre: str, env: dict) -> str:
    return os.getenv(nombre) or env.get(nombre, "")


# ==================== 1. RED ====================

def preparar_red(fw: dict) -> bool:
    print("\n1. Red")
    if fw["WIFI_PASS"] == "cambia-esta-clave":
        aviso("main.cpp todavía tiene la clave de ejemplo de la red: cámbiala en WIFI_PASS")
    prendi_hotspot = not tengo_ip(fw["PC_IP"]) and HOTSPOT_IP.get(SISTEMA) == fw["PC_IP"]
    if prendi_hotspot:
        print(f"  Prendiendo el hotspot '{fw['WIFI_SSID']}'...")
        if SISTEMA == "Windows":
            correr(["powershell", "-ExecutionPolicy", "Bypass", "-File",
                    str(RAIZ / "red" / "windows" / "hotspot.ps1"),
                    "-Ssid", fw["WIFI_SSID"], "-Passphrase", fw["WIFI_PASS"]])
        else:
            correr(["nmcli", "device", "wifi", "hotspot", "ssid", fw["WIFI_SSID"],
                    "password", fw["WIFI_PASS"], "band", "bg"])
        for _ in range(10):
            if tengo_ip(fw["PC_IP"]):
                break
            time.sleep(1)
    if tengo_ip(fw["PC_IP"]):
        ok(f"este computador está en la red del robot, con la IP {fw['PC_IP']}")
        return True
    if prendi_hotspot:
        falta(f"el hotspot no quedó prendido: el error está arriba (red/README.md, {SECCION_RED})")
    elif SISTEMA == "Darwin":
        falta(f"este computador no tiene la IP {fw['PC_IP']}: en macOS el hotspot se prende a mano "
              "(Compartir Internet) o usas el router (red/README.md, sección 3)")
    else:
        falta(f"este computador no tiene la IP {fw['PC_IP']} que pusiste en PC_IP de main.cpp "
              f"(red/README.md, {SECCION_RED})")
    return False


# ==================== 2. MOSQUITTO ====================

def arrancar_mosquitto() -> None:
    print("  Mosquitto está apagado; lo arranco...")
    if SISTEMA == "Windows":
        # Arrancar un servicio pide permisos de administrador: Windows pregunta si lo permites.
        correr(["powershell", "-NoProfile", "-Command",
                "Start-Process powershell -Verb RunAs -Wait "
                "-ArgumentList '-NoProfile','-Command','Start-Service mosquitto'"])
    elif SISTEMA == "Darwin":
        correr(["brew", "services", "start", "mosquitto"])
    else:
        correr(["sudo", "systemctl", "start", "mosquitto"])
    for _ in range(10):
        if puerto_abierto("127.0.0.1", 1883):
            return
        time.sleep(1)


def preparar_mosquitto(fw: dict, hay_red: bool) -> None:
    print("\n2. Mosquitto (MQTT)")
    if not puerto_abierto("127.0.0.1", 1883):
        arrancar_mosquitto()
    if not puerto_abierto("127.0.0.1", 1883):
        falta(f"Mosquitto no arranca: ¿está instalado? (red/README.md, {SECCION_RED})")
    elif not hay_red:
        aviso("Mosquitto está corriendo; sin la red no puedo revisar si el robot lo alcanza")
    elif not puerto_abierto(fw["PC_IP"], 1883):
        falta("Mosquitto solo acepta conexiones de este computador: falta su configuración "
              f"de una sola vez (red/README.md, {SECCION_RED}, Mosquitto)")
    else:
        ok(f"Mosquitto acepta conexiones en {fw['PC_IP']}:1883")
    if SISTEMA == "Windows":
        regla = subprocess.run(["powershell", "-NoProfile", "-Command",
                                "Get-NetFirewallRule -DisplayName 'Pildorin (MQTT y microfono)' "
                                "-ErrorAction SilentlyContinue"], capture_output=True)
        if not regla.stdout.strip():
            aviso("no encontré la regla del firewall 'Pildorin (MQTT y microfono)': sin ella el robot "
                  "no llega al broker ni al micrófono (red/README.md, sección 2, Mosquitto)")


# ==================== 3. MODELO ====================

def revisar_modelo(env: dict) -> None:
    print("\n3. Modelo")
    if variable("PILDORIN_PROVEEDOR", env).strip().lower() == "bedrock":
        if variable("AWS_BEARER_TOKEN_BEDROCK", env):
            ok("Amazon Bedrock, con la API key guardada")
        else:
            falta("PILDORIN_PROVEEDOR es bedrock pero falta AWS_BEARER_TOKEN_BEDROCK (agente/README.md)")
        return
    modelo = variable("PILDORIN_MODELO", env) or "gpt-oss:20b"
    cuerpo = pedir("http://127.0.0.1:11434/api/tags")
    if cuerpo is None:
        falta("Ollama no está corriendo: ábrelo (en Linux: ollama serve)")
        return
    nombres = [m.get("name", "") for m in json.loads(cuerpo).get("models", [])]
    if modelo in nombres or f"{modelo}:latest" in nombres:
        ok(f"Ollama corriendo, con {modelo}")
    else:
        falta(f"Ollama corre pero no tiene {modelo}: ollama pull {modelo}")


# ==================== 4. ROBOT ====================

def responde_ping(ip: str) -> bool:
    if SISTEMA == "Windows":
        r = subprocess.run(["ping", "-n", "1", "-w", "1000", ip], capture_output=True)
        return b"TTL=" in r.stdout.upper()     # Windows contesta 0 aunque no llegue: se mira la respuesta
    espera = "1000" if SISTEMA == "Darwin" else "1"   # en macOS va en milisegundos
    try:
        return subprocess.run(["ping", "-c", "1", "-W", espera, ip], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def revisar_robot(fw: dict, env: dict) -> None:
    print("\n4. Robot")
    ip_agente = variable("PILDORIN_ROBOT_IP", env) or "192.168.137.200"
    if ip_agente != fw["ROBOT_IP"]:
        falta(f"el agente busca al robot en {ip_agente}, pero en main.cpp es {fw['ROBOT_IP']}: "
              f"guarda PILDORIN_ROBOT_IP={fw['ROBOT_IP']} (agente/README.md, Con el robot o la protoboard)")
    if responde_ping(fw["ROBOT_IP"]):
        ok(f"el robot responde en {fw['ROBOT_IP']}")
    else:
        aviso(f"el robot todavía no aparece en {fw['ROBOT_IP']}: enciéndelo y espera el LED azul "
              "(red/README.md, sección 5)")


# ==================== 5. VOZ ====================

def arrancar_voz():
    """Arranca OmniVoice si está instalado. Devuelve el proceso para dejarlo corriendo."""
    print("\n5. Voz")
    if pedir("http://127.0.0.1:5007/salud") is not None:
        ok("OmniVoice ya estaba corriendo")
        return None
    carpeta = RAIZ / "omnivoice"
    if "--kokoro" not in sys.argv and (carpeta / ".venv").exists() and shutil.which("nvidia-smi"):
        print("  Arrancando OmniVoice (la primera vez baja el modelo y tarda varios minutos)...")
        voz = subprocess.Popen(["uv", "run", "servidor_voz.py"], cwd=carpeta)
        while voz.poll() is None:
            if pedir("http://127.0.0.1:5007/salud") is not None:
                ok("OmniVoice listo en 127.0.0.1:5007")
                return voz
            time.sleep(2)
        falta("OmniVoice se cerró al arrancar: el error está arriba (omnivoice/README.md, Si algo falla)")
        return None
    voces = RAIZ / "agente" / "voces"
    if (voces / "kokoro-v1.0.onnx").exists() and (voces / "voices-v1.0.bin").exists():
        ok("Pildorín habla con Kokoro (OmniVoice es opcional: omnivoice/README.md)")
    else:
        falta("no hay voces: en la carpeta agente corre  uv run descargar_voces.py")
    return None


# ==================== TODO JUNTO ====================

def main() -> None:
    nombre = {"Darwin": "macOS"}.get(SISTEMA, SISTEMA)
    print(f"Preparando Pildorín para el robot ({nombre})")
    fw = leer_firmware()
    env = leer_env()

    hay_red = preparar_red(fw)
    preparar_mosquitto(fw, hay_red)
    revisar_modelo(env)
    revisar_robot(fw, env)
    voz = arrancar_voz()

    if faltas:
        cuantas = "Falta 1 cosa" if len(faltas) == 1 else f"Faltan {len(faltas)} cosas"
        print(f"\n{cuantas}: arregla lo marcado con [falta] y vuelve a correr\n    uv run preparar_robot.py")
    else:
        separador = "\\" if SISTEMA == "Windows" else "/"
        con_env = " --env-file ../.env" if (RAIZ / "agente" / ".env").exists() else ""
        print("\nTodo listo. En otra terminal, corre el paso que quieras. Por ejemplo:"
              f"\n    cd agente{separador}paso3_cuerpo\n    uv run{con_env} main.py")
    if voz:
        print("\nDeja esta terminal abierta: aquí corre la voz. Ctrl+C la apaga.")
        try:
            voz.wait()
        except KeyboardInterrupt:
            pass                      # Ctrl+C también le llega al servidor de voz y lo cierra
    raise SystemExit(1 if faltas else 0)


if __name__ == "__main__":
    main()
