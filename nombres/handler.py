from collections import namedtuple as nt
import pygal
from json import loads
from pony import orm
import unicodedata
import urllib
import requests

from data.data import comunes

db = orm.Database()
db.bind(provider="sqlite", filename="data/nombres.db", create_db=True)


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


class Dato(db.Entity):
    año = orm.Required(int)
    nombre = orm.Required(str)
    contador = orm.Required(int)

    def __repr__(self):
        return f"{self.año}:{self.nombre}:{self.contador}"


class Género(db.Entity):
    nombre = orm.Required(str, unique=True)
    masculinidad = orm.Optional(float)


class TotalPorNombre(db.Entity):
    nombre = orm.Required(str)
    contador = orm.Required(int)

    def __repr__(self):
        return f"{self.nombre}:{self.contador}"


@orm.db_session
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


@orm.db_session
def datos_del_año(año):
    # Nombres más populares de ese año
    # Filtramos por prefijo
    filtrado = orm.select(n for n in Dato if n.año == año).order_by(
        orm.desc(Dato.contador)
    )[:50]
    return filtrado


@orm.db_session
def datos_por_prefijo(prefijo):
    # Nombres por prefijo, sin importar el año
    filtrado = orm.select(
        n for n in TotalPorNombre if n.nombre.startswith(prefijo)
    ).order_by(orm.desc(TotalPorNombre.contador))[:50]
    return filtrado


def handle(req):
    """handle a request to the function
    Args:
        req (str): request body
    """

    data = loads(req)
    prefijo = data.get("p") or None
    genero = data.get("g") or None
    try:
        año = int(data.get("a"))
    except Exception:
        año = None

    if prefijo is not None:
        prefijo = prefijo.strip().lower()

    if genero not in ("f", "m"):
        genero = None

    if prefijo is None and año is None:
        datos = datos_globales()
    elif prefijo is None and año is not None:
        datos = datos_del_año(año)
    elif prefijo is not None and año is None:
        datos = datos_por_prefijo(prefijo)
    else:
        # Filtramos por prefijo
        datos = orm.select(
            n for n in Dato if n.año == año and n.nombre.startswith(prefijo)
        ).order_by(orm.desc(Dato.contador))[:50]

    if genero:
        datos = split_por_genero(datos)[genero]
    datos = datos[:10]

    chart = pygal.HorizontalBar(height=400, show_legend=False, show_y_labels=True)
    chart.x_labels = [dato.nombre.title() for dato in datos[::-1]]
    if len(datos) > 1:
        chart.title = f"¿Puede ser ... {datos[0].nombre.title()}? ¿O capaz que {datos[1].nombre.title()}? ¡Contáme más!"
    elif len(datos) == 1:
        chart.title = f"¡Hola {datos[0].nombre.title()}!"
    elif len(datos) < 1:
        chart.title = "¡No esssistís!"
    chart.add("", [dato.contador for dato in datos[::-1]])

    # return Response(chart.render(is_unicode=True), mimetype="image/svg+xml")
    return chart.render(is_unicode=True)
