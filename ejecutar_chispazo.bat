@echo off
@echo off
chcp 65001 >nul
chcp 65001 >nul
REM ============================================================
REM ejecutar_chispazo.bat
REM Se dispara cada 15-20 min desde el Programador de tareas de Windows.
REM 1) Corre el scraper de Chispazo (llama a la pagina oficial y valida
REM    duplicados antes de insertar en Oracle).
REM 2) SOLO si el scraper inserto un sorteo nuevo:
REM    2a) Corre CruceUnosPares (genera recomendados.json + combinaciones)
REM    2b) Corre el .jar principal (genera las paginas HTML y sube
REM        todo a GitHub via GeneradorSubidaGit, incluyendo el
REM        recomendados.json recien generado en el paso 2a)
REM    Si no hubo nada nuevo, no se hace nada mas.
REM
REM NOTA DIAGNOSTICO: revisa el archivo de log despues de cada corrida,
REM ahi quedan los mensajes de error (incluyendo los de subida a Git).
REM ============================================================
REM --- Rutas de Chispazo ---
set RUTA_SCRIPT=C:\grafica01\scraper_chispazo.py
set RUTA_JAR=C:\Users\victor\Documents\NetBeansProjects\Chispazo\dist\Chispazo.jar
set RUTA_LOG=C:\grafica01\log_chispazo.txt
set NOMBRE_CLASE_CRUCE=CruceUnosPares

REM --- Asegura que git.exe este disponible aunque el Programador de tareas
REM     use un PATH distinto al de tu sesion normal ---
set PATH=%PATH%;C:\Program Files\Git\cmd

REM --- Evita que el script de Python pause esperando un Enter ---
set EJECUCION_AUTOMATICA=1

echo ============================================================ >> "%RUTA_LOG%"
echo [%date% %time%] Corriendo scraper de Chispazo... >> "%RUTA_LOG%"
echo RUTA_SCRIPT=%RUTA_SCRIPT% >> "%RUTA_LOG%"
REM python "%RUTA_SCRIPT%" >> "%RUTA_LOG%" 2>&1

python "%RUTA_SCRIPT%" >> "%RUTA_LOG%" 2>&1
set CODIGO=%ERRORLEVEL%

if %CODIGO%==0 (
    echo [%date% %time%] Sorteo nuevo detectado. Generando recomendados.json... >> "%RUTA_LOG%"
    java -cp "%RUTA_JAR%" %NOMBRE_CLASE_CRUCE% >> "%RUTA_LOG%" 2>&1

    echo [%date% %time%] Corriendo el jar principal... >> "%RUTA_LOG%"
    java -jar "%RUTA_JAR%" >> "%RUTA_LOG%" 2>&1
    echo [%date% %time%] Proceso completo. >> "%RUTA_LOG%"
) else if %CODIGO%==1 (
    echo [%date% %time%] Sin novedades, no se corre el jar. >> "%RUTA_LOG%"
) else (
    echo [%date% %time%] ERROR en el scraper ^(codigo %CODIGO%^), revisa la conexion a Oracle o la API. >> "%RUTA_LOG%"
)