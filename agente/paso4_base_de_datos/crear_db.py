"""
Crea pildoras.db con datos de ejemplo. Las fechas son relativas a hoy,
así la demo siempre tiene ventas "de este mes", sin importar cuándo se corra.
db.py la crea sola la primera vez. Para empezar de cero (por ejemplo si cambió
el mes y ya no hay ventas "de este mes"), desde la carpeta del paso:
    uv run crear_db.py
"""

import sqlite3
from datetime import date

CURSOS = [
    ("Python desde cero 2026", 39),
    ("Git para entender, no para memorizar", 29),
    ("Strands Agents", 49),
    ("Databricks 2026", 59),
]

CLIENTES = [
    ("Ana Rojas", "ana@correo.com"),
    ("Luis Pérez", "luis@correo.com"),
    ("Camila Torres", "camila@correo.com"),
    ("Jorge Díaz", "jorge@correo.com"),
]


def crear(ruta: str = "pildoras.db"):
    con = sqlite3.connect(ruta)
    cur = con.cursor()
    cur.executescript("""
        DROP TABLE IF EXISTS ventas;
        DROP TABLE IF EXISTS cursos;
        CREATE TABLE cursos (
            id     INTEGER PRIMARY KEY,
            nombre TEXT NOT NULL,
            precio REAL NOT NULL
        );
        CREATE TABLE ventas (
            id       INTEGER PRIMARY KEY,
            curso_id INTEGER NOT NULL REFERENCES cursos(id),
            cliente  TEXT NOT NULL,
            correo   TEXT NOT NULL,
            monto    REAL NOT NULL,
            fecha    TEXT NOT NULL
        );
    """)
    cur.executemany("INSERT INTO cursos (nombre, precio) VALUES (?, ?)", CURSOS)

    hoy = date.today()
    ventas = []
    # 9 ventas repartidas en los días que van del mes (siempre caen en el mes actual)
    for i in range(9):
        curso_id = (i % len(CURSOS)) + 1
        cliente, correo = CLIENTES[i % len(CLIENTES)]
        precio = CURSOS[curso_id - 1][1]
        fecha = hoy.replace(day=max(1, hoy.day - i * 2)).isoformat()
        ventas.append((curso_id, cliente, correo, precio, fecha))
    cur.executemany(
        "INSERT INTO ventas (curso_id, cliente, correo, monto, fecha) VALUES (?, ?, ?, ?, ?)",
        ventas,
    )
    con.commit()
    con.close()
    print(f"{ruta} creada: {len(CURSOS)} cursos, {len(ventas)} ventas.")


if __name__ == "__main__":
    crear()
