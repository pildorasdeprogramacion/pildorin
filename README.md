# Pildorín

Pildorín es un asistente de escritorio con forma de píldora: escucha, habla, cambia la cara, mueve los brazos, consulta ventas, arma reportes en PDF, manda correos y contesta por Telegram. El cerebro es un agente hecho con Strands Agents; el cuerpo, un ESP32-S3 con tres pantallas redondas, micrófono, parlante y dos servos.

Aquí está todo para armarlo: el agente, el firmware del robot y la configuración de la red, para Windows, macOS y Linux.

## Tres formas de hacer el laboratorio

| Forma | Qué necesitas | Por dónde empiezas |
|---|---|---|
| Solo computador | El computador, con micrófono y parlantes | [agente](agente/README.md) |
| Protoboard | El ESP32-S3 y los módulos montados en protoboard | [firmware](firmware/README.md), después [red](red/README.md) y [agente](agente/README.md) |
| Robot | Pildorín armado | igual que la protoboard |

El modelo puede correr en tu computador con Ollama (gpt-oss:20b, pide 16 GB de RAM) o en Amazon Bedrock (Claude Sonnet 4.6) con una API key. Las dos opciones están en la guía del [agente](agente/README.md).

## Qué hay en cada carpeta

| Carpeta | Qué es | Herramientas |
|---|---|---|
| [`agente/`](agente/README.md) | El agente en Python, en 6 pasos: del hola mundo al asistente que manda reportes por Telegram | VS Code, uv, Ollama o Amazon Bedrock |
| [`firmware/`](firmware/README.md) | El programa del ESP32-S3: ojos, boca, brazos, micrófono, parlante, Wi-Fi y MQTT | VS Code con PlatformIO |
| [`red/`](red/README.md) | Cómo se conectan el robot y el computador: hotspot o router, y el broker Mosquitto | Mosquitto |
| [`omnivoice/`](omnivoice/README.md) | Opcional: el servidor de voz con emociones (risas, suspiros) que usa el agente | uv, tarjeta NVIDIA |

## Preparar todo para el robot

Cada vez que vayas a trabajar con el robot o la protoboard, desde la carpeta del repositorio, en Windows, macOS o Linux:

```
uv run preparar_robot.py
```

Prende el hotspot (en Windows y Linux; en macOS se prende a mano), arranca Mosquitto y la voz OmniVoice si la instalaste, y revisa el modelo, la IP del robot y si el robot ya está en la red. El nombre y la clave de la red los toma de `firmware/src/main.cpp`. Lo que falte lo marca con `[falta]` y te dice en qué guía está. Si arrancó OmniVoice, deja esa terminal abierta y corre el agente en otra. Con `--kokoro` no arranca OmniVoice y la memoria de la tarjeta gráfica queda para Ollama.

Antes, una sola vez: graba el [firmware](firmware/README.md) e instala y configura Mosquitto ([red](red/README.md)).

## Cómo se hablan las piezas

```
 Robot (ESP32-S3)                         Computador
 micrófono    -- audio, TCP 5005 -------> agente: Whisper -> modelo -> tools
 parlante     <------- audio, TCP 5006 -- agente: voz (OmniVoice o Kokoro)
 ojos, brazos <-- MQTT pildorin/comando -- Mosquitto (1883) <-- agente: tools
```

Sin robot, el agente usa el micrófono y los parlantes del computador, y los comandos de la cara y los brazos se muestran en la consola.

## Descargar

- Con git: en GitHub, botón verde **Code**, copia la dirección y corre `git clone` con ella.
- Sin git: **Code > Download ZIP** y descomprímelo.

En Windows, ponlo en una carpeta que no esté dentro de OneDrive (por ejemplo `C:\cursos\pildorin`): OneDrive intenta sincronizar los miles de archivos que se instalan y todo se pone lento.
