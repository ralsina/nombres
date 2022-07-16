import pygal
from json import loads

db = orm.Database()
db.bind(provider="sqlite", filename="nombres.db", create_db=True)


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


def handle(req):
    """handle a request to the function
    Args:
        req (str): request body
    """

    data = loads(req)
    prefijo = data.get("p") or None
    genero = data.get("g") or None
    try:
        año = int(request.args.get("a"))
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
        chart.title = f"¡No esssistís!"
    chart.add("", [dato.contador for dato in datos[::-1]])

    return Response(chart.render(is_unicode=True), mimetype="image/svg+xml")

