"""
Envío de correo por SMTP. Las credenciales van en variables de entorno:

    SMTP_HOST   (ej. smtp.gmail.com)
    SMTP_PORT   (587)
    SMTP_USER   (tu correo)
    SMTP_PASS   (app password, no la clave normal)
    CORREO_YO   (opcional: a dónde va "envíamelo a mí")

Si no están configuradas, el correo NO se envía: se guarda como archivo .eml
en salida/ y la tool lo dice. Así la demo nunca se cae por el SMTP.

Los correos de "mándaselo a Pepe" salen de agente/contactos.json.
"""

import json
import os
import re
import smtplib
import unicodedata
from email.message import EmailMessage
from pathlib import Path

SALIDA = "salida"

# Contactos (nombre -> correo) en la carpeta agente. contactos.json no se sube a GitHub;
# si no existe, se usa el de ejemplo, con correos @example.com que no le llegan a nadie.
CONTACTOS = Path(__file__).resolve().parent.parent / "contactos.json"
CONTACTOS_EJEMPLO = CONTACTOS.with_name("contactos.ejemplo.json")

VALIDO = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+$")


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _palabras(texto: str) -> list[str]:
    return re.findall(r"\w+", _sin_acentos(texto.lower()))


def buscar_contacto(nombre: str) -> list[tuple[str, str]]:
    """Los contactos que coinciden con el nombre: el exacto si lo hay; si no, los que
    comparten una palabra ("maría" encuentra a "María López")."""
    ruta = CONTACTOS if CONTACTOS.exists() else CONTACTOS_EJEMPLO
    try:
        contactos = json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"{ruta.name} tiene un error en la línea {e.lineno}: "
                         "revisa las comillas y las comas") from e
    dicho = _palabras(nombre)
    exactos = [(n, c) for n, c in contactos.items() if _palabras(n) == dicho]
    return exactos or [(n, c) for n, c in contactos.items() if set(dicho) & set(_palabras(n))]


def enviar(destinatario: str, asunto: str, cuerpo: str, adjunto: str | None = None) -> str:
    """Devuelve siempre un string: qué pasó. Nunca levanta excepción, para que
    el modelo lea el motivo y decida (reintentar o avisar)."""
    destinatario = destinatario.strip()
    if not VALIDO.match(destinatario):
        return f"La dirección '{destinatario}' no es válida: revísala en contactos.json o en CORREO_YO."

    msg = EmailMessage()
    msg["From"] = os.getenv("SMTP_USER", "pildorin@pildorasdeprogramacion.com")
    msg["To"] = destinatario
    msg["Subject"] = asunto
    msg.set_content(cuerpo)
    if adjunto:
        with open(adjunto, "rb") as f:
            msg.add_attachment(f.read(), maintype="application", subtype="pdf",
                               filename=os.path.basename(adjunto))

    host, user, pwd = os.getenv("SMTP_HOST"), os.getenv("SMTP_USER"), os.getenv("SMTP_PASS")
    if not (host and user and pwd):
        os.makedirs(SALIDA, exist_ok=True)
        ruta = os.path.join(SALIDA, "correo.eml")
        with open(ruta, "wb") as f:
            f.write(bytes(msg))
        return f"SMTP no configurado; el correo para {destinatario} quedó guardado en {ruta}"

    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT") or "587"), timeout=15) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
    except smtplib.SMTPAuthenticationError:
        return "El servidor rechazó usuario o contraseña (revisa SMTP_USER y SMTP_PASS)."
    except (smtplib.SMTPException, OSError) as e:
        return f"No pude enviar el correo: {e}"
    return f"Correo enviado a {destinatario}"