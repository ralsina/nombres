from collections import namedtuple as nt
import pygal
from json import loads
from pony import orm
import unicodedata
import urllib
import requests
from pathlib import Path

db = orm.Database()
db_path = Path(__file__).parent / "data" / "nombres.db"
db.bind(provider="sqlite", filename=str(db_path), create_db=False)


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


comunes = [
    (2864022, "maria"),
    (1449833, "juan"),
    (843572, "carlos"),
    (818420, "jose"),
    (654373, "jorge"),
    (584357, "luis"),
    (507297, "ana"),
    (450100, "pablo"),
    (415770, "miguel"),
    (403384, "diego"),
    (390227, "cristian"),
    (383734, "lucas"),
    (379099, "daniel"),
    (373629, "matias"),
    (370481, "sergio"),
    (361771, "hector"),
    (353198, "silvia"),
    (334132, "gustavo"),
    (331263, "claudia"),
    (313310, "marcelo"),
    (312935, "roberto"),
    (303012, "juan carlos"),
    (297554, "mario"),
    (296081, "oscar"),
    (289390, "fernando"),
    (286297, "francisco"),
    (284980, "santiago"),
    (282100, "ricardo"),
    (279980, "nicolas"),
    (279701, "franco"),
    (275715, "rosa"),
    (274311, "alejandro"),
    (271442, "norma"),
    (270951, "andrea"),
    (267742, "natalia"),
    (266892, "eduardo"),
    (261842, "marta"),
    (261577, "victor"),
    (261511, "miguel angel"),
    (259138, "graciela"),
    (255319, "hugo"),
    (254235, "ramon"),
    (251358, "julio"),
    (250673, "walter"),
    (249755, "laura"),
    (247685, "pedro"),
    (241669, "patricia"),
    (241264, "martin"),
    (239907, "camila"),
    (237393, "florencia"),
    (233677, "facundo"),
    (232581, "monica"),
    (232185, "gabriela"),
    (231470, "gabriel"),
    (230553, "ruben"),
    (227598, "angel"),
    (225576, "claudio"),
    (220958, "sofia"),
    (215451, "susana"),
    (213005, "raul"),
    (212155, "rocio"),
    (208673, "sandra"),
    (208050, "alberto"),
    (207491, "alicia"),
    (207422, "romina"),
    (206394, "marcos"),
    (205059, "federico"),
    (204450, "mirta"),
    (197139, "leonardo"),
    (195351, "lucia"),
    (195269, "maximiliano"),
    (195202, "leandro"),
    (194177, "micaela"),
    (194030, "carlos alberto"),
    (192391, "liliana"),
    (192353, "veronica"),
    (191577, "rodrigo"),
    (191009, "mariana"),
    (190076, "agustin"),
    (187952, "gonzalo"),
    (187486, "guillermo"),
    (187142, "adriana"),
    (186071, "sebastian"),
    (182370, "carolina"),
    (181401, "javier"),
    (180527, "lautaro"),
    (176959, "maría"),
    (174959, "jose luis"),
    (174648, "daniela"),
    (172991, "nestor"),
    (172394, "marcela"),
    (172306, "agustina"),
    (166278, "ana maria"),
    (165752, "antonio"),
    (162899, "juana"),
    (162865, "maria del"),
    (160986, "ignacio"),
    (159978, "milagros"),
    (157342, "cesar"),
    (156010, "luciano"),
    (155853, "ariel"),
    (155517, "julieta"),
    (154694, "lorena"),
    (154209, "alejandra"),
    (151612, "manuel"),
    (150930, "mariano"),
    (147977, "daiana"),
    (146569, "valeria"),
    (144877, "valentina"),
    (144183, "joaquin"),
    (143869, "paula"),
    (142186, "olga"),
    (138102, "cecilia"),
    (137277, "victoria"),
    (136360, "martina"),
    (135298, "tomas"),
    (135179, "jonathan"),
    (134909, "luciana"),
    (134902, "noelia"),
    (134470, "mariela"),
    (132103, "thiago"),
    (131974, "carmen"),
    (129464, "paola"),
    (128502, "maria cristina"),
    (128363, "ramona"),
    (128259, "gladys"),
    (128218, "elsa"),
    (127278, "david"),
    (126498, "luis alberto"),
    (125852, "lidia"),
    (125823, "carla"),
    (124014, "nelida"),
    (123736, "andres"),
    (123641, "esteban"),
    (119739, "ezequiel"),
    (118139, "dario"),
    (117768, "nancy"),
    (117466, "alfredo"),
    (117058, "juan manuel"),
    (116021, "adrian"),
    (115739, "yanina"),
    (115661, "analia"),
    (115414, "maria de"),
    (114780, "mauro"),
    (114533, "vanesa"),
    (114257, "cristina"),
    (112961, "mateo"),
    (110535, "mercedes"),
    (108885, "enrique"),
    (108582, "teresa"),
    (107808, "cintia"),
    (107571, "karina"),
    (107364, "beatriz"),
    (106706, "mauricio"),
    (106221, "alexis"),
    (105871, "benjamin"),
    (104823, "horacio"),
    (104701, "brenda"),
    (104141, "viviana"),
    (103167, "hernan"),
    (103142, "omar"),
    (102947, "maria del carmen"),
    (102056, "alan"),
    (101654, "blanca"),
    (101602, "gaston"),
    (101477, "sonia"),
    (101188, "brian"),
    (101167, "juan pablo"),
    (100564, "osvaldo"),
    (99016, "karen"),
    (98747, "silvana"),
    (98689, "ivan"),
    (97816, "silvina"),
    (97652, "yamila"),
    (97540, "margarita"),
    (97460, "marina"),
    (97077, "miriam"),
    (96320, "jesica"),
    (95977, "julia"),
    (95871, "angela"),
    (95652, "rodolfo"),
    (94561, "bruno"),
    (94335, "gisela"),
    (93301, "stella"),
    (92538, "kevin"),
    (92476, "juan jose"),
    (90330, "enzo"),
    (89970, "nahuel"),
    (89119, "eliana"),
    (89069, "catalina"),
    (89043, "santino"),
    (88971, "irma"),
    (88244, "julian"),
    (87741, "estela"),
    (87589, "sara"),
    (87345, "jonatan"),
    (87220, "stella maris"),
    (86501, "sabrina"),
    (86483, "fabian"),
    (85476, "yesica"),
]
