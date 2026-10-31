# Pildorín · la voz con OmniVoice

OmniVoice (de k2-fsa) clona una voz a partir de un audio corto y entiende etiquetas de emoción como `[laughter]` o `[sigh]`: con eso Pildorín se ríe, suspira y se sorprende de verdad. Es la voz que usamos con el robot.

Es **opcional**. Si este servidor no está corriendo, el agente habla con Kokoro y todo funciona igual, solo que sin las emociones en la voz.

El agente no carga OmniVoice. Este servidor corre aparte, en su propia carpeta y su propio entorno, y el agente le pide cada frase por HTTP en `127.0.0.1:5007`. Así torch con CUDA, que pesa varios GB, no entra al entorno del agente.

## Lo que necesitas

- Una tarjeta gráfica NVIDIA con los drivers al día, en Windows o Linux. En macOS no funciona: ahí el agente usa Kokoro.
- [uv](https://docs.astral.sh/uv/), el mismo del agente. Este servidor usa Python 3.12 (fijado en `.python-version`) y uv lo descarga si no lo tienes.
- Espacio en disco para torch con CUDA y el modelo de OmniVoice: varios GB.

## Instalación (una sola vez)

Desde la carpeta del repositorio:

```
cd omnivoice
uv sync
```

Baja Python 3.12, torch 2.8 con CUDA 12.8 (desde el índice de PyTorch) y OmniVoice. Tarda según tu conexión.

## Arrancar el servidor

```
cd omnivoice
uv run servidor_voz.py
```

La primera vez descarga el modelo `k2-fsa/OmniVoice` de Hugging Face y prepara la voz de Pildorín (crea `pildorin_voz.pt`). Las siguientes veces arranca más rápido. Cuando diga:

```
Servidor de voz en http://127.0.0.1:5007  (Ctrl+C para salir)
```

deja esa terminal abierta y corre el agente en otra (**Terminal > Nuevo terminal**). Al arrancar, el agente tiene que decir `Voz: OmniVoice (servidor local).`

Arranca siempre el servidor primero: el agente revisa una sola vez, al arrancar, si OmniVoice está disponible.

Con el robot, `uv run preparar_robot.py` (desde la carpeta del repositorio) lo arranca solo, junto con la red y Mosquitto, y espera a que esté listo.

Para probar solo la voz, con el servidor corriendo, en otra terminal:

```
cd agente/paso2_oidos_y_voz
uv run voz.py
```

## La voz de Pildorín

La voz sale de `refs/ENERGIA_M1.wav` y su transcripción `refs/ENERGIA_M1.txt`: 14 segundos de un hombre de Colombia diciendo tres frases con energía, del conjunto de datos libre OpenSLR 72. OmniVoice copia el timbre y el ánimo de esa referencia. Los detalles de la fuente están en `refs/ATRIBUCION.txt`.

`pildorin_voz.pt` es esa misma voz ya procesada por el modelo. Se crea sola la primera vez y no se sube a git.

Para usar otra voz:

1. Pon en `refs/` un `.wav` corto (unos 5 a 15 segundos, una sola persona, sin música ni ruido) y un `.txt` con el mismo nombre que diga exactamente lo que se escucha en el audio. Usa una voz que tengas derecho a usar.
2. En `servidor_voz.py`, cambia `ENERGIA_M1` en la línea `REF = RAIZ / "refs" / "ENERGIA_M1"` por el nombre de tus archivos, sin la extensión.
3. Borra `pildorin_voz.pt` y vuelve a arrancar el servidor.

## Ajustes

| Dónde | Qué | Valor |
|---|---|---|
| `servidor_voz.py` | `NUM_STEP`: pasos de generación | `32` = mejor calidad, `16` = más rápido |
| `agente/paso*/voz.py` | `OMNIVOICE_VELOCIDAD`: menos de 1 le da más tiempo a cada frase | `0.8` |

## Etiquetas que entiende

`[laughter]` risa, `[sigh]` suspiro, `[surprise-oh]` y `[surprise-ah]` sorpresa, `[question-ah]` duda, `[confirmation-en]` asentir, `[dissatisfaction-hnn]` fastidio. El system prompt del agente le enseña a usarlas desde el paso 2; Kokoro y Piper las ignoran.

## Si algo falla

**`torch no ve una GPU NVIDIA`.** No hay tarjeta NVIDIA o faltan sus drivers. Sin este servidor, el agente usa Kokoro.

**El agente dice `Voz: Kokoro.`** El servidor no estaba listo cuando arrancó el agente. Espera a que el servidor diga `Servidor de voz en http://127.0.0.1:5007` y vuelve a arrancar el agente.

**Se corta el final de las frases.** OmniVoice decide cuánto dura el audio antes de generarlo, y si la frase no cabe se pierde el final. Baja `OMNIVOICE_VELOCIDAD` en `voz.py` del agente (por ejemplo a `0.7`), en los pasos que uses.

**El agente responde muy lento con Ollama y OmniVoice a la vez.** Los dos comparten la memoria de la tarjeta gráfica. Si no alcanza, Windows usa memoria del sistema y el modelo se vuelve mucho más lento: en el portátil del laboratorio, gpt-oss:20b bajó de unos 65 a unos 12 tokens por segundo. Usa Amazon Bedrock para el modelo, o apaga este servidor y quédate con Kokoro (con el robot: `uv run preparar_robot.py --kokoro`).

**`uv sync` falla bajando torch.** torch con CUDA viene de `download.pytorch.org`: revisa que tu red no lo bloquee y vuelve a correrlo.

## Licencias

- OmniVoice: Apache 2.0 ([k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice)).
- Voz de referencia: CC BY-SA 4.0, OpenSLR 72, Copyright 2018, 2019 Google, Inc. ([openslr.org/72](https://www.openslr.org/72/)). Si la usas, conserva `refs/ATRIBUCION.txt`.
