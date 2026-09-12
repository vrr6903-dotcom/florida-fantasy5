import time
import subprocess
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import oracledb

# ----------------------
# CONFIGURACIÓN
# ----------------------
USUARIO = "SYSTEM"
CONTRASEÑA = "Ren69034"
CONEXION = "localhost:1521/XE"
TABLA = "CHISPA28"
URL_SITIO = "https://www.loterianacional.gob.mx/Chispazo/Resultados"

# Ruta de tu archivo .bat a ejecutar tras el éxito
BAT_PATH = r"C:\FTP\blog01.bat"

MAX_INTENTOS = 40
TIEMPO_ESPERA_SEGUNDOS = 300  # 5 minutos


# ----------------------
# FUNCIÓN PARA OBTENER EL ÚLTIMO CONCURSO GUARDADO
# ----------------------
def obtener_ultimo_concurso_db():
    try:
        conn = oracledb.connect(user=USUARIO, password=CONTRASEÑA, dsn=CONEXION)
        cur = conn.cursor()
        cur.execute(f"SELECT NVL(MAX(CONCURSO), 0) FROM {TABLA}")
        max_concurso = cur.fetchone()[0]
        cur.close()
        conn.close()
        return max_concurso
    except Exception as e:
        print(f"⚠️ No se pudo consultar el último concurso en BD: {str(e)}")
        return 0


# ----------------------
# FUNCIÓN DE EXTRACCIÓN HTML
# ----------------------
def traer_ultimos_sorteos(cantidad=2):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(URL_SITIO, headers=headers, timeout=20)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        filas = soup.find_all("tr")
        
        if not filas:
            print("⚠️ No se encontraron filas en el documento HTML.")
            return []

        datos = []
        for fila in filas:
            texto_fila = fila.get_text(" ", strip=True)
            tokens = texto_fila.replace("\xa0", " ").split()
            
            numeros_enteros = []
            for t in tokens:
                t_limpio = t.replace(",", "")
                if t_limpio.isdigit():
                    numeros_enteros.append(int(t_limpio))
            
            if len(numeros_enteros) >= 6:
                concurso = numeros_enteros[0]
                
                if concurso > 12000:
                    fecha_str = next((t for t in tokens if "/" in t and len(t) == 10), None)
                    if not fecha_str:
                        continue
                    
                    comb = numeros_enteros[1:6]
                    
                    if all(1 <= n <= 28 for n in comb):
                        registro = (concurso, fecha_str, comb[0], comb[1], comb[2], comb[3], comb[4])
                        if registro not in datos:
                            datos.append(registro)
            
            if len(datos) >= cantidad:
                break

        return datos

    except Exception as e:
        print(f"❌ Error al leer la página: {str(e)}")
        return []


# ----------------------
# FUNCIÓN PARA GUARDAR EN ORACLE
# ----------------------
def cargar_en_oracle(lista_datos):
    if not lista_datos:
        return False

    try:
        conn = oracledb.connect(user=USUARIO, password=CONTRASEÑA, dsn=CONEXION)
        cur = conn.cursor()

        for reg in lista_datos:
            cur.execute(f"""
                MERGE INTO {TABLA} t
                USING (
                    SELECT :p1 AS CONCURSO,
                           TO_DATE(:p2, 'DD/MM/YYYY') AS FECHA,
                           :p3 AS R1, :p4 AS R2, :p5 AS R3, :p6 AS R4, :p7 AS R5
                    FROM DUAL
                ) s
                ON (t.CONCURSO = s.CONCURSO)
                WHEN MATCHED THEN UPDATE
                    SET t.FECHA = s.FECHA, t.R1 = s.R1, t.R2 = s.R2,
                        t.R3 = s.R3, t.R4 = s.R4, t.R5 = s.R5
                WHEN NOT MATCHED THEN INSERT
                    (CONCURSO, FECHA, R1, R2, R3, R4, R5)
                    VALUES (s.CONCURSO, s.FECHA, s.R1, s.R2, s.R3, s.R4, s.R5)
            """, reg)
            print(f"➡️ Procesado en Oracle: Concurso {reg[0]}")

        conn.commit()
        cur.close()
        conn.close()
        print("✅ Todos los datos guardados correctamente en Oracle.")
        return True

    except Exception as e:
        print(f"❌ Error en base de datos: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False


# ----------------------
# EJECUCIÓN PRINCIPAL CON REINTENTOS
# ----------------------
if __name__ == "__main__":
    intento = 1
    nuevo_encontrado = False
    print(f" ------CHISPA 28  NUMEROS-------")
    ultimo_concurso_db = obtener_ultimo_concurso_db()
    print(f"📌 Último concurso en BD ({TABLA}): {ultimo_concurso_db}")

    while intento <= MAX_INTENTOS:
        hora_actual = datetime.now().strftime("%H:%M:%S")
        print(f"\n🔍 [{hora_actual}] Intento {intento} de {MAX_INTENTOS}...")

        resultados = traer_ultimos_sorteos(cantidad=2)

        if resultados:
            sorteos_nuevos = [r for r in resultados if r[0] > ultimo_concurso_db]

            if sorteos_nuevos:
                print(f"🎉 ¡Se encontraron {len(sorteos_nuevos)} concurso(s) nuevo(s)!")
                for s in sorteos_nuevos:
                    print(f"   Sorteo {s[0]} | Fecha {s[1]} | Números: {s[2:]}")

                if cargar_en_oracle(sorteos_nuevos):
                    nuevo_encontrado = True
                    # Al confirmar la inserción exitosa, ejecuta el .bat
                    print("⏳ sin ejecutar Bat")
                    break
            else:
                print("⏳ No hay registros nuevos aún.")
        else:
            print("⚠️ No se pudieron extraer datos en este intento.")

        if intento < MAX_INTENTOS:
            print(f"😴 Esperando {TIEMPO_ESPERA_SEGUNDOS // 60} minutos para el siguiente intento...")
            time.sleep(TIEMPO_ESPERA_SEGUNDOS)

        intento += 1

    if not nuevo_encontrado:
        print(f"\n⏹️ Se alcanzaron los {MAX_INTENTOS} intentos sin detectar concursos nuevos.")

    # input("\nPresiona Enter para salir...")