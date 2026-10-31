"""
Cuerpo de Pildorín: cada comando viaja por MQTT (broker Mosquitto) y el firmware
del ESP32 lo ejecuta. Sin robot (--sin-robot) el comando solo se muestra en consola.
"""

import json
import os
import sys

import paho.mqtt.client as mqtt

BROKER = "localhost"   # el broker corre en tu misma PC
TOPIC = "pildorin/comando"
TOPIC_ESTADO = "pildorin/estado/conectado"   # el robot publica 1 al conectar; si se cae, el broker publica 0

# Sin robot (uv run main.py --sin-robot o PILDORIN_SIN_ROBOT=1) no se usa MQTT.
SIN_ROBOT = "--sin-robot" in sys.argv or os.getenv("PILDORIN_SIN_ROBOT") == "1"

_robot = {"conectado": None}   # None = todavía no se sabe (el robot no ha publicado su estado)


def _al_conectar(client, userdata, flags, reason_code, properties):
    if not reason_code.is_failure:
        client.subscribe(TOPIC_ESTADO)   # al reconectar se vuelve a suscribir


def _al_mensaje(client, userdata, msg):
    if msg.topic == TOPIC_ESTADO:
        _robot["conectado"] = msg.payload.strip() == b"1"


_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
_client.on_connect = _al_conectar
_client.on_message = _al_mensaje
if not SIN_ROBOT:
    _client.reconnect_delay_set(min_delay=1, max_delay=5)
    _client.connect_async(BROKER, 1883)   # si Mosquitto todavía no está, se conecta cuando aparezca
    _client.loop_start()


def robot_conectado() -> bool:
    """True si hay broker y el robot no avisó que se desconectó."""
    return _client.is_connected() and _robot["conectado"] is not False


def enviar_comando(accion: str, **params) -> bool:
    """Publica un comando para el cuerpo del robot.
    Devuelve False si no hay broker o si el robot está desconectado.
    Sin robot, el comando solo se muestra en la consola."""
    payload = json.dumps({"accion": accion, **params})
    if SIN_ROBOT:
        print(f"    (sin robot) {TOPIC} {payload}")
        return True
    if not robot_conectado():
        return False
    return _client.publish(TOPIC, payload, qos=1).rc == mqtt.MQTT_ERR_SUCCESS


GESTOS = {"celebrar", "saludar", "pensar", "triste", "reposo"}
LADOS = {"izq", "der", "ambos"}


def gesto_brazos(gesto: str) -> bool:
    """Coreografía fija con los dos brazos; la ejecuta el firmware (gestoBrazos en main.cpp)."""
    if gesto not in GESTOS:
        return False
    return enviar_comando("brazos", gesto=gesto)


def mover_brazo(lado: str, angulo: int) -> bool:
    """Control directo de un brazo: lado izq|der|ambos, ángulo 20..160, 90 = reposo."""
    if lado not in LADOS:
        return False
    angulo = max(20, min(160, int(angulo)))
    return enviar_comando("brazo", lado=lado, angulo=angulo)
