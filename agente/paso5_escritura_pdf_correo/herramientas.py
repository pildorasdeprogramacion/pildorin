"""
Tools del paso 5: cuerpo + lectura (paso 4) + ESCRITURA en la BD + reporte PDF + correo.
Con estas tres nuevas el agente puede encadenar varias tools en un solo objetivo.
"""

import os
from datetime import date

from strands import tool

import db
import correo
import reporte
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


# ---------- base de datos: escritura ----------

@tool
def registrar_venta(curso: str, cliente: str, correo_cliente: str) -> str:
    """Registra una venta nueva. El monto es el precio del curso.
    Args:
        curso: nombre (o parte del nombre) del curso vendido.
        cliente: nombre de la persona que compró.
        correo_cliente: correo de la persona que compró.
    """
    log_tool("registrar_venta", curso=curso, cliente=cliente, correo_cliente=correo_cliente)
    fila = db.obtener_uno(
        "SELECT id, nombre, precio FROM cursos WHERE lower(nombre) LIKE ?",
        (f"%{curso.lower()}%",),
    )
    if not fila:
        return f"No encontré ningún curso que se parezca a '{curso}'. Usa listar_cursos."
    venta_id = db.ejecutar(
        "INSERT INTO ventas (curso_id, cliente, correo, monto, fecha) VALUES (?, ?, ?, ?, ?)",
        (fila["id"], cliente, correo_cliente, fila["precio"], date.today().isoformat()),
    )
    return f"Venta #{venta_id} registrada: {cliente} compró '{fila['nombre']}' por {fila['precio']:.0f} USD"


# ---------- reporte y correo ----------

@tool
def generar_reporte_pdf() -> str:
    """Genera el reporte de ventas del mes actual en PDF, con el logo de la academia.
    Devuelve la ruta del archivo generado, que se puede adjuntar con enviar_correo."""
    log_tool("generar_reporte_pdf")
    ventas = _ventas_mes()
    ruta = os.path.join("salida", f"reporte_ventas_{date.today():%Y_%m}.pdf")
    reporte.generar_pdf(ventas, ruta)
    return f"Reporte generado en {ruta} ({len(ventas)} ventas)"


@tool
def enviar_correo(destinatario: str, asunto: str, cuerpo: str, adjunto: str = "") -> str:
    """Envía un correo a un contacto. Si hay un archivo para adjuntar, pasa su ruta en
    adjunto (por ejemplo la ruta que devolvió generar_reporte_pdf).
    destinatario: el nombre del contacto tal como lo dijo el usuario ("Pepe", "María");
    la tool busca su correo. Si dice "envíamelo", "a mi correo" o "a mí", pasa "yo"."""
    log_tool("enviar_correo", destinatario=destinatario, asunto=asunto, adjunto=adjunto)
    if destinatario.strip().lower() in ("yo", "mi correo", "mí"):
        direccion = os.getenv("CORREO_YO", "")
        if not direccion:
            return "No sé cuál es tu correo: falta la variable CORREO_YO."
    elif "@" in destinatario or "arroba" in destinatario.lower():
        return "Solo le escribo a contactos: pide que agreguen esa dirección a agente/contactos.json con un nombre."
    else:
        contactos = correo.buscar_contacto(destinatario)
        if not contactos:
            return f"No tengo a '{destinatario}' en los contactos (agente/contactos.json)."
        if len(contactos) > 1:
            return f"Hay varios contactos con ese nombre: {', '.join(n for n, _ in contactos)}. Pregunta a cuál."
        direccion = contactos[0][1]
    if adjunto and not os.path.exists(adjunto):
        return f"El adjunto {adjunto} no existe. Genera el reporte primero."
    return correo.enviar(direccion, asunto, cuerpo, adjunto or None)

TOOLS_CUERPO = [poner_cara, mover_brazos, mover_un_brazo]
TOOLS_LECTURA = [listar_cursos, ventas_del_mes, total_ventas_mes]
TOOLS_ESCRITURA = [registrar_venta, generar_reporte_pdf, enviar_correo]
