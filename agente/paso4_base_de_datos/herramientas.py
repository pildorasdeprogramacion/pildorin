"""
Tools del paso 4: el cuerpo (igual que el paso 3) + LECTURA de la base de datos.
Solo lectura. Si le piden registrar una venta, el agente no tiene con qué.
"""

from strands import tool

import db
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


# ---------- base de datos: lectura ----------

def _ventas_mes() -> list[dict]:
    return db.obtener_todos("""
        SELECT v.fecha, v.cliente, c.nombre AS curso, v.monto
        FROM ventas v JOIN cursos c ON c.id = v.curso_id
        WHERE strftime('%Y-%m', v.fecha) = strftime('%Y-%m', 'now', 'localtime')
        ORDER BY v.fecha
    """)


@tool
def listar_cursos() -> str:
    """Lista los cursos de Píldoras de Programación con su precio en dólares."""
    log_tool("listar_cursos")
    cursos = db.obtener_todos("SELECT nombre, precio FROM cursos ORDER BY id")
    return "\n".join(f"- {c['nombre']}: {c['precio']:.0f} USD" for c in cursos)


@tool
def ventas_del_mes() -> str:
    """Devuelve todas las ventas del mes actual, una por línea: fecha, cliente,
    curso y monto. Sirve para responder cualquier pregunta sobre ventas:
    quién compró un curso, qué compró alguien, cuántas veces se vendió algo.
    Llámala y filtra tú la respuesta a partir de las líneas."""
    log_tool("ventas_del_mes")
    filas = _ventas_mes()
    if not filas:
        return "No hay ventas este mes."
    return "\n".join(
        f"{f['fecha']} · {f['cliente']} · {f['curso']} · {f['monto']:.0f} USD" for f in filas
    )


@tool
def total_ventas_mes() -> str:
    """Total vendido en el mes actual (cantidad de ventas y suma en dólares)."""
    log_tool("total_ventas_mes")
    r = db.obtener_uno("""
        SELECT COUNT(*) AS n, COALESCE(SUM(monto), 0) AS total
        FROM ventas WHERE strftime('%Y-%m', fecha) = strftime('%Y-%m', 'now', 'localtime')
    """)
    return f"{r['n']} ventas este mes por un total de {r['total']:.0f} USD"


TOOLS_CUERPO = [poner_cara, mover_brazos, mover_un_brazo]
TOOLS_LECTURA = [listar_cursos, ventas_del_mes, total_ventas_mes]
