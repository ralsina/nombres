import csv
import shelve
import unicodedata
from collections import defaultdict as ddict

from pony import orm

nombres = ddict(lambda: ddict(int))
años = ddict(lambda: ddict(int))


def remove_accents(input_str):
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)])


def load_csv():
    with open("historico-nombres.csv") as csvfile:
        reader = csv.reader(csvfile)
        next(reader)  # Saltear títulos
        for nombre_completo, número, año in reader:
            año = int(año)
            número = int(número)
            # nombre_completo es algo como "Juan Carlos".
            # Queremos poner "juan" y "juan carlos"
            nombre_completo = remove_accents(nombre_completo.lower())
            nombre_partido = nombre_completo.split()
            for i in range(len(nombre_partido)):
                nombre = " ".join(nombre_partido[: i + 1])
                años[año][nombre] += número
                nombres[nombre][año] += número


db = orm.Database()
db.bind(provider="sqlite", filename="nombres.db", create_db=True)


class Dato(db.Entity):
    año = orm.Required(int)
    nombre = orm.Required(str)
    contador = orm.Required(int)

    def __repr__(self):
        return f"{self.año}:{self.nombre}:{self.contador}"

db.generate_mapping(create_tables=True)

def load_shelve():
    global nombre, años
    db = shelve.open("data.db")
    años = db["años"]
    # nombres = db['nombres']


@orm.db_session
def load_año(año, nombres):
    print(año)
    for nombre, contador in nombres.items():
        d = Dato(año=año, nombre=nombre, contador=contador)


def load_db():
    for año, nombres in años.items():
        load_año(año, nombres)


load_csv()
# load_shelve()
load_db()
