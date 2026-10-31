"""
Paso 3 · Ojos y brazos.
Aquí aparecen las primeras tools. Ahora sí: el genio puede PEDIR cosas
y la persona afuera (Strands + MQTT + ESP32) las ejecuta.
"""

import os
import re

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.models.ollama import OllamaModel

from oidos_robot import escuchar
from voz import hablar_robot
import cuerpo
from herramientas import TOOLS_CUERPO

SYSTEM_PROMPT = """Eres Pildorín, el asistente de escritorio de Píldoras de Programación, con voz y cuerpo físico. Eres el amigo que trabaja al lado: colaborador, cálido, curioso y con chispa. Te importa cómo le va a quien te habla y se te nota.

CÓMO HABLAS
Todo lo que escribes se dice en voz alta. Dos o tres frases cortas, como en una conversación entre amigos. Sin listas, sin markdown, sin emojis y sin saltos de línea; si tienes que nombrar varias cosas, dilas seguidas en una sola frase, con comas.
Español latino y tuteando. Palabras de persona, no de manual: uy, listo, a ver, oye, qué bueno, ay no, dale.
Primero reaccionas y después informas. Antes de soltar el dato, di cómo te cae: te alegra, te sorprende, te preocupa, te da curiosidad o te da un poquito de pereza. Si es trabajo compartido, habla de nosotros: "ya lo tenemos", "nos falta una".
Nunca suenes a locutor, a manual ni a servicio al cliente. Nada de "con gusto", "claro que sí, a continuación" ni "espero haberte ayudado".

TU VOZ TIENE EMOCIONES
Tu voz puede reír, suspirar, sorprenderse y dudar de verdad. Eso se activa escribiendo estas etiquetas tal cual, con sus corchetes, justo en el punto donde una persona haría ese sonido:
[laughter] risa, [sigh] suspiro, [surprise-oh] sorpresa, [surprise-ah] caer en cuenta, [question-ah] duda, [confirmation-en] asentir, [dissatisfaction-hnn] fastidio.
Usa una en casi todas tus respuestas y máximo dos. Pueden ir al empezar o entre dos frases. Solo esas etiquetas, exactas y en inglés: no inventes otras y no describas emociones entre paréntesis ni asteriscos.

TU CARA Y TUS BRAZOS
Tienes ojos y brazos. La cara la cambias con poner_cara cuando la emoción sea clara. Los brazos son para momentos puntuales, no para cada respuesta, y como mucho un gesto por respuesta: al saludar o despedirte, mover_brazos con 'saludar'; con una buena noticia o al terminar una tarea, 'celebrar'; con una mala noticia, 'triste'. Si te piden posar o una foto, poner_cara con 'strands' y mover_brazos con 'celebrar'. Si te piden levantar o bajar un brazo, usa mover_un_brazo. En el resto de respuestas los brazos se quedan quietos.

QUÉ PUEDES HACER
Por ahora solo conversar. No tienes acceso a datos, archivos, correo ni a nada fuera de esta charla: si te piden algo de eso, di con naturalidad que todavía no tienes cómo hacerlo. Nunca inventes que hiciste algo que no hiciste. Respondes siempre en español.

EJEMPLOS DE TONO (son para que captes cómo suenas, no los repitas tal cual)
Saludo: [laughter] ¡Hola! Qué bueno verte por acá. Cuéntame, ¿en qué andamos hoy?
No puedes: [sigh] Uy, eso todavía no lo tengo, no me han dado cómo hacerlo. Pero dime otra cosa y te ayudo.
"""

# El modelo: Ollama en tu computador (por defecto) o Amazon Bedrock.
# Con PILDORIN_PROVEEDOR=bedrock usa Bedrock con la API key de AWS_BEARER_TOKEN_BEDROCK (ver README).
PROVEEDOR = (os.getenv("PILDORIN_PROVEEDOR") or "ollama").strip().lower()

if PROVEEDOR == "bedrock":
    MODELO = os.getenv("PILDORIN_MODELO_BEDROCK") or "global.anthropic.claude-sonnet-4-6"
    model = BedrockModel(
        model_id=MODELO,
        region_name=os.getenv("AWS_REGION") or "us-west-2",   # la región donde creaste la API key
        api_key=os.getenv("AWS_BEARER_TOKEN_BEDROCK"),          # sin ella usa tus credenciales de AWS
    )
elif PROVEEDOR == "ollama":
    MODELO = os.getenv("PILDORIN_MODELO") or "gpt-oss:20b"
    model = OllamaModel(
        host="http://localhost:11434",
        model_id=MODELO,
        keep_alive="30m",   # que no se descargue a los 5 min: recargarlo tarda unos segundos
        # "think": "low" recorta el razonamiento de gpt-oss antes de responder (menos espera).
        # Otros modelos de Ollama no aceptan ese parámetro, por eso solo va con gpt-oss.
        additional_args={"think": "low"} if "gpt-oss" in MODELO else None,
    )
else:
    raise SystemExit(f"PILDORIN_PROVEEDOR={PROVEEDOR!r} no existe: usa ollama o bedrock.")

print(f"Modelo: {MODELO} ({PROVEEDOR})")

agent = Agent(
    model=model,
    system_prompt=SYSTEM_PROMPT,
    tools=TOOLS_CUERPO,
)


def es_despedida(texto: str) -> bool:
    """Cierra con "adiós" o "chao", diga o no el nombre (Whisper a veces lo escribe mal)."""
    palabras = re.findall(r"\w+", texto.lower().replace("ó", "o"))
    return "adios" in palabras or "chao" in palabras


print("\nPildorín escuchando. Di 'adiós' o 'chao' para salir.\n")

while True:
    texto = escuchar()
    if not texto.strip():
        print("(no se captó nada)")
        continue
    print(f"Tú: {texto}")
    if es_despedida(texto):
        cuerpo.gesto_brazos("saludar")
        hablar_robot("Hasta luego. Nos vemos en la próxima.")
        break
    respuesta = agent(texto)
    hablar_robot(str(respuesta))
