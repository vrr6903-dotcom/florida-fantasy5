from datetime import datetime
import os

import oracledb
import requests

# Configuración de la conexión a la Base de Datos Oracle.
# Las credenciales se leen de variables de entorno si existen (DB_USER/DB_PASS);
# si no, se usan estos valores por defecto (igual que en tus otros scripts).
DB_USER = os.environ.get("DB_USER", "SYSTEM")
DB_PASSWORD = os.environ.get("DB_PASS", "Ren69034")
DB_DSN = "localhost:1521/XE"

# API oficial (encontrada inspeccionando el Network de floridalottery.com):
# devuelve el ÚLTIMO sorteo de cada juego, incluyendo FANTASY 5 (Id 113).
API_URL = "https://apim-website-prod-eastus.azure-api.net/drawgamesapp/getLatestDrawGames"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML,"
        " like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def obtener_resultados_fantasy5():
  """Llama a la API oficial y devuelve los sorteos de FANTASY 5 (Evening y Midday)
  ya parseados, listos para insertar. No inventa ni asume ningún valor: si un
  campo no viene como se espera, ese sorteo se ignora y se avisa por consola."""
  try:
    response = requests.get(API_URL, headers=HEADERS, timeout=15)
  except requests.RequestException as e:
    print(f"Error de red al conectar con la API de Florida Lottery: {e}")
    return []

  if response.status_code != 200:
    print(f"Error al conectar con la API: {response.status_code}")
    return []

  try:
    data = response.json()
  except ValueError:
    print("La API no devolvió un JSON válido.")
    return []

  resultados = []
  for juego in data:
    if juego.get("GameName") != "FANTASY 5":
      continue
    if "DrawNumbers" not in juego:
      continue

    numeros = sorted(n["NumberPick"] for n in juego["DrawNumbers"])
    if len(numeros) != 5:
      print(f"FANTASY 5 con {len(numeros)} números en vez de 5, se ignora: {juego}")
      continue

    # Fecha viene como "09/04/2026 12:00:00 AM" -> la convertimos a YYYY-MM-DD.
    try:
      fecha = datetime.strptime(juego["DrawDate"], "%m/%d/%Y %I:%M:%S %p").strftime("%Y-%m-%d")
    except (KeyError, ValueError) as e:
      print(f"No se pudo interpretar la fecha del sorteo, se ignora: {e}")
      continue

    draw_type = (juego.get("DrawType") or "").upper()
    if draw_type == "EVENING":
      h = "E"
    elif draw_type == "MIDDAY":
      h = "D"
    else:
      print(f"DrawType desconocido para FANTASY 5 ('{draw_type}'), se ignora este registro.")
      continue

    resultados.append({
        "r1": numeros[0], "r2": numeros[1], "r3": numeros[2],
        "r4": numeros[3], "r5": numeros[4],
        "fecha": fecha,
        "h": h,
    })

  # Orden cronológico: Midday siempre antes que Evening del mismo día
  # (mismo orden que ya usa tu tabla FANTASY: concurso menor = midday).
  orden_h = {"D": 0, "E": 1}
  resultados.sort(key=lambda r: (r["fecha"], orden_h[r["h"]]))
  return resultados


def ya_existe_sorteo(cursor, fecha, h):
  """Valida contra la BD si YA existe un registro para esa fecha+sorteo,
  para no insertar duplicados ni inventar un concurso nuevo de más."""
  cursor.execute(
      "SELECT COUNT(*) FROM SYSTEM.FANTASY WHERE FECHA = TO_DATE(:fecha, 'YYYY-MM-DD') AND H = :h",
      {"fecha": fecha, "h": h},
  )
  return cursor.fetchone()[0] > 0


def guardar_y_procesar():
  resultados = obtener_resultados_fantasy5()
  if not resultados:
    print("No se obtuvieron resultados de FANTASY 5 desde la API.")
    return

  try:
    connection = oracledb.connect(user=DB_USER, password=DB_PASSWORD, dsn=DB_DSN)
    cursor = connection.cursor()

    cursor.execute("SELECT NVL(MAX(CONCURSO), 0) FROM SYSTEM.FANTASY")
    siguiente_concurso = cursor.fetchone()[0] + 1

    sql_insert = """
        INSERT INTO SYSTEM.FANTASY (CONCURSO, R1, R2, R3, R4, R5, FECHA, H)
        VALUES (:concurso, :r1, :r2, :r3, :r4, :r5, TO_DATE(:fecha, 'YYYY-MM-DD'), :h)
    """

    insertados = 0
    for r in resultados:
      if ya_existe_sorteo(cursor, r["fecha"], r["h"]):
        print(f"Ya existe un registro para {r['fecha']} ({r['h']}), se omite (sin duplicar).")
        continue

      cursor.execute(sql_insert, {
          "concurso": siguiente_concurso,
          "r1": r["r1"], "r2": r["r2"], "r3": r["r3"], "r4": r["r4"], "r5": r["r5"],
          "fecha": r["fecha"],
          "h": r["h"],
      })
      print(f"Insertado concurso {siguiente_concurso}: {r['fecha']} ({r['h']}) -> "
            f"{r['r1']},{r['r2']},{r['r3']},{r['r4']},{r['r5']}")
      siguiente_concurso += 1
      insertados += 1

    connection.commit()
    print(f"Listo. Se insertaron {insertados} sorteo(s) nuevo(s).")

  except Exception as e:
    print(f"Error en la base de datos Oracle: {e}")
  finally:
    if "cursor" in locals():
      cursor.close()
    if "connection" in locals():
      connection.close()


if __name__ == "__main__":
  guardar_y_procesar()
  input("Presiona Enter para salir...")