"""
Paso 1 · Hola mundo agente.
Solo dos piezas: el model (gpt-oss:20b en Ollama, o Claude Sonnet 4.6 en Amazon Bedrock)
y el system prompt.
Sin tools. Se habla con él por consola.
"""

import os

from strands import Agent
from strands.models.bedrock import BedrockModel
from strands.models.ollama import OllamaModel

SYSTEM_PROMPT = "Eres Pildorín, un asistente de escritorio. Respondes en español, en una o dos frases, sin listas ni markdown."

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

agent = Agent(model=model, system_prompt=SYSTEM_PROMPT, callback_handler=None)

print("Pildorín (paso 1). Escribe 'salir' para terminar.\n")

while True:
    texto = input("Tú: ").strip()
    if not texto:
        continue
    if texto.lower() == "salir":
        break
    respuesta = agent(texto)
    print(f"Pildorín: {respuesta}\n")
