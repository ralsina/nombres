import unicodedata
import urllib
from collections import namedtuple as nt
from dataclasses import dataclass
from json import loads

import pygal
import pymysql
import pymysql.cursors
import requests

connection = pymysql.connect(
    host="10.61.0.1",
    user="root",
    password="",
    database="nombres",
    cursorclass=pymysql.cursors.DictCursor,
)


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


@dataclass
class Género:
    nombre: str = ""
    masculinidad: float = 0


def split_por_genero(nombres):
    no_clasificados = set()
    # Veamos cuales de estos nombres ya están clasificados
    for nombre in nombres:
        clasificador = remove_accents(
            nombre.nombre.split()[0]
        )  # genderize no aprecia acentos para AR
        genero = Género.get(nombre=clasificador)
        if not genero:
            # No está clasificado
            no_clasificados.add(urllib.parse.quote(clasificador))

    if no_clasificados:
        print(f"Tengo {len(no_clasificados)} sin clasificar")
        no_clasificados = list(no_clasificados)
        # Averiguar los no clasificados
        # Partimos en bloques de a 10 (API de genderize)
        for i in range(len(no_clasificados) // 10 + 1):
            chunk = no_clasificados[i * 10 : (i + 1) * 10]
            url = f'https://api.genderize.io/?name[]={"&name[]=".join(chunk)}&country_id=AR'
            clasificados = requests.get(url)
            for resultado in clasificados.json():
                if not resultado["name"]:
                    continue  # No me importa
                if resultado["gender"] == "male":
                    masc = resultado["probability"]
                elif resultado["gender"] == "female":
                    masc = 1 - resultado["probability"]
                else:
                    # Probablemente un acento o algo así
                    print(f"Raro:{resultado}")
                    masc = None
                # Metemos en la base
                print(f"Clasificando {resultado}: {masc}")
                Género(nombre=resultado["name"], masculinidad=masc)

    nombres_f = []
    nombres_m = []
    for nombre in nombres:
        clasificador = remove_accents(nombre.nombre.split()[0])
        genero = Género.get(nombre=clasificador)
        if not genero or genero.masculinidad is None:  # No clasificado, en ambos
            nombres_f.append(nombre)
            nombres_m.append(nombre)
        elif 0.4 < genero.masculinidad:
            nombres_m.append(nombre)
        elif 0.6 > genero.masculinidad:
            nombres_f.append(nombre)
    return {"f": nombres_f, "m": nombres_m}


def datos_globales():
    # Datos falsos
    Dato = nt("Dato", ["contador", "nombre"])
    return [Dato(contador=x[0], nombre=x[1]) for x in comunes][:50]


def handle(req):
    """handle a request to the function
    Args:
        req (str): request body

    {
        p: prefijo del nombre,
        g: genero del nombre,
        a: año de nacimiento
    }

    """
    try:
        data = loads(req)
        prefijo = data.get("p") or None
        genero = data.get("g") or None
        try:
            año = int(data.get("a"))
        except Exception:
            año = None
    except Exception:
        prefijo = genero = año = None

    if prefijo is not None:
        prefijo = prefijo.strip().lower()

    if genero not in ("f", "m"):
        genero = None

    if prefijo is None and año is None:
        with connection.cursor() as cursor:
            sql = """
                SELECT SUM(contador) AS total, nombre
                FROM nombre
                GROUP BY nombre 
                ORDER BY total DESC
                LIMIT 50
                """
            cursor.execute(sql)
            datos = [(r["total"], r["nombre"]) for r in cursor.fetchall()]

    elif prefijo is None and año is not None:
        with connection.cursor() as cursor:
            sql = """
                SELECT contador, nombre FROM nombre
                WHERE
                    anio = %s
                ORDER BY contador DESC
                LIMIT 50
                """
            cursor.execute(sql, (año,))
            datos = [(r["contador"], r["nombre"]) for r in cursor.fetchall()]

    elif prefijo is not None and año is None:
        with connection.cursor() as cursor:
            sql = """
                SELECT contador, nombre FROM nombre
                WHERE
                    nombre LIKE %s
                ORDER BY contador DESC
                LIMIT 50
                """
            cursor.execute(sql, (f"{prefijo}%",))
            datos = [(r["contador"], r["nombre"]) for r in cursor.fetchall()]
    else:
        with connection.cursor() as cursor:
            sql = """
                SELECT contador, nombre FROM nombre
                WHERE
                    anio = %s AND
                    nombre LIKE %s
                ORDER BY contador DESC
                LIMIT 50
                """
            cursor.execute(sql, (año, f"{prefijo}%"))
            datos = [(r["contador"], r["nombre"]) for r in cursor.fetchall()]

    if genero:
        datos = split_por_genero(datos)[genero]

    datos = datos[:10]

    chart = pygal.HorizontalBar(height=400, show_legend=False, show_y_labels=True)
    chart.x_labels = [nombre.title() for _, nombre in datos[::-1]]
    if len(datos) > 1:
        chart.title = f"¿Puede ser ... {datos[0][1].title()}? ¿O capaz que {datos[1][1].title()}? ¡Contáme más!"
    elif len(datos) == 1:
        chart.title = f"¡Hola {datos[0][1].title()}!"
    elif len(datos) < 1:
        chart.title = "¡No esssistís!"
    chart.add("", [contador for contador, _ in datos[::-1]])

    # return Response(chart.render(is_unicode=True), mimetype="image/svg+xml")
    return chart.render(is_unicode=True), 200, {"Content-Type": "image/svg+xml"}
