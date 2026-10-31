"""
Capa de datos. Una conexión por operación (closing) porque Strands puede
ejecutar varias tools en paralelo dentro del mismo turno.
Si pildoras.db no existe, se crea con datos de ejemplo la primera vez que se usa.
"""

import os
import sqlite3
import threading
from contextlib import closing

import crear_db

DB = "pildoras.db"
_creando = threading.Lock()   # dos tools a la vez no pueden crear la base al mismo tiempo


def _conectar():
    with _creando:
        if not os.path.exists(DB):
            crear_db.crear(DB)
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


def obtener_todos(sql: str, params: tuple = ()) -> list[dict]:
    with closing(_conectar()) as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def obtener_uno(sql: str, params: tuple = ()) -> dict | None:
    with closing(_conectar()) as con:
        fila = con.execute(sql, params).fetchone()
        return dict(fila) if fila else None


def ejecutar(sql: str, params: tuple = ()) -> int:
    """Ejecuta INSERT/UPDATE/DELETE y devuelve el id de la última fila."""
    with closing(_conectar()) as con:
        cur = con.execute(sql, params)
        con.commit()
        return cur.lastrowid
