@echo off
cd /d "%~dp0"
echo Instalando dependencias (solo la primera vez puede tardar)...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo No se encontro "python". Prueba reemplazando "python" por "py" en este archivo,
  echo o instala Python desde https://www.python.org/downloads/ marcando "Add to PATH".
  pause
  exit /b 1
)
echo.
echo Iniciando servidor en http://localhost:8000 ...
echo Deja esta ventana abierta mientras usas el dashboard.
echo.
python -m uvicorn main:app --reload --port 8000
pause
