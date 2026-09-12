@echo off
REM ============================================================
REM ejecutar_fantasy5.bat
REM Se dispara cada 15-20 min desde el Programador de tareas de Windows.
REM 1) Corre el scraper de Fantasy 5 (llama a la API oficial y valida
REM    duplicados antes de insertar en Oracle).
REM 2) SOLO si el scraper insertó un sorteo nuevo, corre el .jar de Java
REM    (que ya genera las 6 páginas HTML y sube todo a GitHub vía
REM    GeneradorSubidaGit). Si no hubo nada nuevo, no se hace nada más,
REM    para no gastar tiempo ni hacer commits de Git vacíos.
REM
REM NOTA DIAGNÓSTICO: se agregó log a archivo porque al correr desde el
REM Programador de tareas no hay ventana visible y se perdían los mensajes
REM de error (incluyendo los de la subida a Git). Revisa
REM C:\grafica01\log_fantasy5.txt después de cada corrida.
REM ============================================================
REM --- Ajusta estas 2 rutas a las tuyas ---
set RUTA_SCRIPT=C:\grafica01\Fchispa28_fantasy5_auto.py
set RUTA_JAR=C:\Users\victor\Documents\NetBeansProjects\Graficas21\dist\Graficas21.jar
set RUTA_LOG=C:\grafica01\log_fantasy5.txt

REM --- Asegura que git.exe esté disponible aunque el Programador de tareas
REM     use un PATH distinto al de tu sesión normal. Ajusta la ruta si tu
REM     Git está instalado en otro lado (verifica con "where git" en tu consola). ---
set PATH=%PATH%;C:\Program Files\Git\cmd

REM --- Le indica al script de Python que no debe pausar esperando un Enter
REM     (esa pausa es solo para cuando lo corres tú mismo con doble clic). ---
set EJECUCION_AUTOMATICA=1

echo ============================================================ >> "%RUTA_LOG%"
echo [%date% %time%] Corriendo scraper de Fantasy 5... >> "%RUTA_LOG%"
python "%RUTA_SCRIPT%" >> "%RUTA_LOG%" 2>&1
set CODIGO=%ERRORLEVEL%

if %CODIGO%==0 (
    echo [%date% %time%] Sorteo nuevo detectado. Corriendo el jar de Java... >> "%RUTA_LOG%"
    java -jar "%RUTA_JAR%" >> "%RUTA_LOG%" 2>&1
    echo [%date% %time%] Proceso completo. >> "%RUTA_LOG%"
) else if %CODIGO%==1 (
    echo [%date% %time%] Sin novedades, no se corre el jar. >> "%RUTA_LOG%"
) else (
    echo [%date% %time%] ERROR en el scraper ^(codigo %CODIGO%^), revisa la conexion a Oracle o la API. >> "%RUTA_LOG%"
)
