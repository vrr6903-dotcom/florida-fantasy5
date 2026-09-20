from datetime import datetime
import os
import re
import sys

import oracledb
import requests
from bs4 import BeautifulSoup

# Configuración de la conexión a la Base de Datos Oracle.
# Las credenciales se leen de variables de entorno si existen (DB_USER/DB_PASS);
# si no, se usan estos valores por defecto (igual que en tus otros scripts).
DB_USER = os.environ.get("DB_USER", "SYSTEM")
DB_PASSWORD = os.environ.get("DB_PASS", "Ren69034")
DB_DSN = "localhost:1521/XE"

TABLA = "SYSTEM.CHISPA28"
URL_SITIO = "https://www.loterianacional.gob.mx/Chispazo/Resultados"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def obtener_resultados_chispazo():
  """Descarga la página de Resultados y devuelve TODOS los sorteos que logre
  reconocer (normalmente el actual + el histórico de "Últimos 15 sorteos"),
  como una lista de dicts {concurso, fecha, r1..r5}. No inventa ni asume la
  letra H aquí — eso se decide después, contra la BD (ver determinar_h).

  El parseo es por tokens (no depende de clases/ids del HTML, que pueden
  cambiar) igual que ya venía funcionando en el script anterior de números:
  cada <tr> se convierte en texto, se extraen los números enteros, y si hay
  al menos 6 (concurso + 5 resultados) y los 5 últimos caben en 1-28, se
  toma como un sorteo válido.
  """
  try:
    resp = requests.get(URL_SITIO, headers=HEADERS, timeout=20)
    resp.raise_for_status()
  except requests.RequestException as e:
    print(f"Error de red al conectar con loterianacional.gob.mx: {e}")
    return []

  soup = BeautifulSoup(resp.text, "html.parser")
  filas = soup.find_all("tr")
  if not filas:
    print("No se encontraron filas en el HTML de la página.")
    return []

  resultados = []
  vistos = set()
  for fila in filas:
    texto_fila = fila.get_text(" ", strip=True)
    tokens = texto_fila.replace("\xa0", " ").split()

    numeros_enteros = []
    for t in tokens:
      t_limpio = t.replace(",", "")
      if t_limpio.isdigit():
        numeros_enteros.append(int(t_limpio))

    if len(numeros_enteros) < 6:
      continue

    concurso = numeros_enteros[0]
    if concurso <= 12000:
      continue

    fecha_str = next((t for t in tokens if "/" in t and len(t) == 10), None)
    if not fecha_str:
      continue

    comb = numeros_enteros[1:6]
    if not all(1 <= n <= 28 for n in comb):
      continue

    if concurso in vistos:
      continue
    vistos.add(concurso)

    try:
      fecha = datetime.strptime(fecha_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
      print(f"Fecha con formato inesperado, se ignora ese sorteo: {fecha_str}")
      continue

    resultados.append({
        "concurso": concurso,
        "fecha": fecha,
        "r1": comb[0], "r2": comb[1], "r3": comb[2], "r4": comb[3], "r5": comb[4],
    })

  resultados.sort(key=lambda r: r["concurso"])
  return resultados


def ya_existe_concurso(cursor, concurso):
  """CHISPA28 no tiene llave primaria, así que hay que validar manualmente
  que ese concurso no exista ya antes de insertar (evita duplicados)."""
  cursor.execute(f"SELECT COUNT(*) FROM {TABLA} WHERE CONCURSO = :c", {"c": concurso})
  return cursor.fetchone()[0] > 0


def determinar_h(cursor, fecha):
  """Chispazo saca 2 sorteos por día y el sitio NO indica cuál es cuál
  (no hay ninguna etiqueta "Clásico"/"De las tres" en la página). Confirmado
  contra tu histórico en CHISPA28: entre los 2 concursos de un mismo día, el
  de NÚMERO MENOR es "De las tres" (H='T') y el MAYOR es "Clásico" (H='N').

  Por eso la letra H se decide aquí contando cuántos registros ya existen
  en la BD para esa fecha (NO por la hora del reloj, que es como lo hacía
  el script anterior y podía fallar):
    - 0 registros ya guardados para esa fecha -> es el primer sorteo del día -> 'T'
    - 1 registro ya guardado para esa fecha    -> es el segundo sorteo del día -> 'N'
    - 2 o más -> ya están completos los 2 de ese día; se devuelve None y el
      caller debe omitir ese registro (no debería pasar en condiciones normales).
  """
  cursor.execute(
      f"SELECT COUNT(*) FROM {TABLA} WHERE FECHA = TO_DATE(:f, 'YYYY-MM-DD')",
      {"f": fecha},
  )
  cantidad = cursor.fetchone()[0]
  if cantidad == 0:
    return "T"
  elif cantidad == 1:
    return "N"
  else:
    return None


def guardar_y_procesar():
  """Devuelve la cantidad de sorteos nuevos insertados (0 si no había nada
  nuevo, -1 si hubo un error de BD)."""
  resultados = obtener_resultados_chispazo()
  if not resultados:
    print("No se obtuvieron resultados de Chispazo desde la página.")
    return 0

  insertados = 0
  try:
    connection = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
    cursor = connection.cursor()

    cursor.execute(f"SELECT NVL(MAX(CONCURSO), 0) FROM {TABLA}")
    ultimo_concurso_db = cursor.fetchone()[0]
    print(f"Último concurso en BD ({TABLA}): {ultimo_concurso_db}")

    sql_insert = f"""
        INSERT INTO {TABLA} (CONCURSO, R1, R2, R3, R4, R5, FECHA, H)
        VALUES (:concurso, :r1, :r2, :r3, :r4, :r5, TO_DATE(:fecha, 'YYYY-MM-DD'), :h)
    """

    for r in resultados:
      if r["concurso"] <= ultimo_concurso_db:
        continue
      if ya_existe_concurso(cursor, r["concurso"]):
        print(f"El concurso {r['concurso']} ya existe en BD, se omite (sin duplicar).")
        continue

      h = determinar_h(cursor, r["fecha"])
      if h is None:
        print(f"Ya hay 2 sorteos guardados para {r['fecha']}, no se puede determinar "
              f"la letra H del concurso {r['concurso']}; se omite y se revisa a mano.")
        continue

      cursor.execute(sql_insert, {
          "concurso": r["concurso"],
          "r1": r["r1"], "r2": r["r2"], "r3": r["r3"], "r4": r["r4"], "r5": r["r5"],
          "fecha": r["fecha"],
          "h": h,
      })
      print(f"Insertado concurso {r['concurso']}: {r['fecha']} (H={h}) -> "
            f"{r['r1']},{r['r2']},{r['r3']},{r['r4']},{r['r5']}")
      insertados += 1

    connection.commit()
    print(f"Listo. Se insertaron {insertados} sorteo(s) nuevo(s).")

  except Exception as e:
    print(f"Error en la base de datos Oracle: {e}")
    return -1
  finally:
    if "cursor" in locals():
      cursor.close()
    if "connection" in locals():
      connection.close()

  return insertados


if __name__ == "__main__":
  cantidad = guardar_y_procesar()

  # Mismo estándar de códigos de salida que el script de Fantasy 5:
  #   0 = hubo sorteo(s) nuevo(s) -> el .bat corre el jar de Java
  #   1 = sin novedades -> el .bat no hace nada más
  #   2 = error (ya se imprimió el detalle arriba)
  if cantidad > 0:
    codigo_salida = 0
  elif cantidad == 0:
    codigo_salida = 1
  else:
    codigo_salida = 2

  if os.environ.get("EJECUCION_AUTOMATICA") != "1":
    input("Presiona Enter para salir...")

  sys.exit(codigo_salida)