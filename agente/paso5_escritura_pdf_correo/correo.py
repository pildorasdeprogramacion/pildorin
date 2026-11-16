"""
Envío de correo por SMTP. Las credenciales van en variables de entorno:

    SMTP_HOST   (ej. smtp.gmail.com)
    SMTP_PORT   (587)
    SMTP_USER   (tu correo)
    SMTP_PASS   (app password, no la clave normal)
    CORREO_YO   (opcional: a dónde va "envíamelo a mí")

Si no están configuradas, el correo NO se envía: se guarda como archivo .eml
en salida/ y la tool lo dice. Así la demo nunca se cae por el SMTP.

Los correos de "mándaselo a Pepe" salen de agente/contactos.json. El correo del
cliente que se dicta al registrar una venta lo deja bien escrito correo_dictado.
"""

import difflib
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


# Lo que puede pasar el modelo cuando le piden "envíamelo", "a mí" o "a mi correo".
_PARA_MI = {"yo", "mi", "me", "mismo", "a", "para", "correo", "electronico", "email"}


def es_para_mi(destinatario: str) -> bool:
    palabras = set(_palabras(destinatario))
    return bool(palabras & {"yo", "mi", "me"}) and palabras <= _PARA_MI


# ---------- correo dictado (el del cliente, al registrar una venta) ----------

# Dominios que más se dictan. Si Whisper entiende mal uno ("jotmail", "outluk",
# "gmail punto con"), se cambia por el más parecido. Van también dominios reales que
# se parecen a otros (mail.com, ymail.com, gmx.com) para que no se "corrijan".
DOMINIOS = [
    "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com", "live.com",
    "hotmail.es", "outlook.es", "yahoo.es", "msn.com", "mail.com", "ymail.com",
    "gmx.com", "aol.com", "me.com", "proton.me", "protonmail.com",
    "yahoo.com.mx", "hotmail.com.ar", "yahoo.com.ar", "outlook.com.mx",
]

# Cómo escribe Whisper un correo dictado ("maria arroba gmail punto com"), en orden.
DICTADO = [
    (r"[¿?¡!,;:\"'()]", " "),                    # signos que agrega Whisper
    (r"\s*(guion bajo|raya al piso)\s*", "_"),
    (r"\s*guion medio\s*", "-"),
    (r"\s*(arrobar?|a roba)\s*", "@"),           # a veces lo escribe "arrobar"
    (r"\s*punto\s*", "."),
    (r"\s*guion\s*", "-"),
    (r"@+", "@"),
    (r"\s+", ""),
    (r"\.{2,}", "."),
    (r"\.+$", ""),                               # el punto final de la frase
    # gmail, yahoo y outlook escritos como suenan en español ("yi-meil", "ya-jú", "aut-luk")
    (r"@(jmail|gemail|gimeil|jimeil|yimeil|jimail|yimail)(?=\.|$)", "@gmail"),
    (r"@(yaju|yahu)(?=\.|$)", "@yahoo"),
    (r"@(autluk|autluc|outluc)(?=\.|$)", "@outlook"),
]


def correo_dictado(texto: str) -> str:
    """El correo escrito a partir de lo que dejó Whisper: "María arroba Gmail punto
    com." -> maria@gmail.com. Si el dominio se parece mucho a uno común, lo cambia por
    ese ("jotmail.com" -> hotmail.com). Sin "punto com" ("arroba gmail") asume .com."""
    d = _sin_acentos(texto.strip().lower())
    for patron, nuevo in DICTADO:
        d = re.sub(patron, nuevo, d)
    usuario, _, dominio = d.partition("@")
    if not (usuario and dominio):
        return d                                 # sin arroba o sin dominio: no es un correo
    if "." not in dominio:
        dominio += ".com"
    if dominio not in DOMINIOS:
        parecido = difflib.get_close_matches(dominio, DOMINIOS, n=1, cutoff=0.8)
        if parecido:
            dominio = parecido[0]
    return f"{usuario}@{dominio}"


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
