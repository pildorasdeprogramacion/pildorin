"""
Tools del cuerpo de Pildorín. Cada una publica un comando por MQTT y el
firmware del ESP32 lo ejecuta. Es lo primero que el agente puede PEDIR.
"""

from strands import tool

from cuerpo import GESTOS, enviar_comando, gesto_brazos, mover_brazo

EMOCIONES = {
    "neutral", "feliz", "sorprendido", "guino", "triste", "enojado",
    "dormido", "amor", "pensando", "error", "strands",
}


def log_tool(nombre: str, **args) -> None:
    detalle = ", ".join(f"{k}={v!r}" for k, v in args.items())
    print(f"    -> tool {nombre}({detalle})")


# ---------- cuerpo ----------

@tool
def poner_cara(emocion: str) -> str:
    """Cambia la expresión de los ojos del robot.
    Opciones: neutral, feliz, sorprendido, guino, triste, enojado, dormido,
    amor, pensando, error, strands.
    'strands' muestra el logo de Strands Agents en los ojos: úsala cuando te
    pidan posar, una foto, o saludar al patrocinador."""
    log_tool("poner_cara", emocion=emocion)
    if emocion not in EMOCIONES:
        return f"Emoción inválida. Usa: {', '.join(sorted(EMOCIONES))}"
    ok = enviar_comando("ojos", emocion=emocion)
    return f"Expresando: {emocion}" if ok else "Sin conexión con el cuerpo."


@tool
def mover_brazos(gesto: str) -> str:
    """Hace un gesto con los dos brazos del robot.
    Opciones: celebrar (alegría, éxito, buenas noticias, posar para una foto),
    saludar (hola o adiós, con el brazo derecho), pensar (reflexión, brazo izquierdo),
    triste (malas noticias, ambos caídos), reposo (volver a neutral)."""
    log_tool("mover_brazos", gesto=gesto)
    if gesto not in GESTOS:
        return f"Gesto inválido. Usa: {', '.join(sorted(GESTOS))}"
    ok = gesto_brazos(gesto)
    return f"Gesto ejecutado: {gesto}" if ok else "Sin conexión con el cuerpo."


@tool
def mover_un_brazo(lado: str, angulo: int) -> str:
    """Mueve UN brazo a un ángulo exacto. lado: 'izq', 'der' o 'ambos'.
    angulo: 20 a 160; 90 es reposo, 150 arriba, 30 abajo.
    Úsala cuando pidan levantar o bajar un brazo concreto."""
    log_tool("mover_un_brazo", lado=lado, angulo=angulo)
    ok = mover_brazo(lado, angulo)
    return f"Brazo {lado} en {angulo}°" if ok else "Lado inválido o sin conexión con el cuerpo."


TOOLS_CUERPO = [poner_cara, mover_brazos, mover_un_brazo]
