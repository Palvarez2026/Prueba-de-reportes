# EERR Mina RA — prototipo Python + React

Prototipo que reemplaza la lógica de fórmulas del Excel `EERR2_v4_Ago2026 UV_corregido.xlsx`
por un motor de cálculo en Python, expuesto vía API REST (FastAPI) y con un dashboard en
React servido por el mismo backend (un solo servicio, un solo comando).

## Estructura

```
backend/
  engine.py           # logica de calculo del EERR mensual (cascada, variaciones, YTD)
  daily.py            # logica de Ingreso Diario / Resumen Diario (dia a dia)
  main.py             # API REST (FastAPI) + sirve el dashboard
  data.json           # datos del EERR mensual (Presupuesto Jun-Dic 2026, Real hasta Agosto)
  ingreso_diario.json # datos diarios cargados por operadores (seed con Ago 2026)
  requirements.txt
  static/
    index.html           # dashboard EERR (React via CDN)
    ingreso_diario.html  # formulario para que operadores carguen datos del dia
    resumen_diario.html  # resumen presup vs real del dia + avance mes/semana
frontend/
  index.html        # copia identica del dashboard EERR, por si prefieres correrlo como servicio aparte
```

## Como correrlo en tu computador

```
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Abre **http://localhost:8000** en el navegador. Ya está: un solo comando, un solo puerto,
dashboard y API en el mismo lugar.

## Como compartirlo con otra persona (link publico)

Ver la guia de despliegue que te dio Claude en el chat (Render, gratis). En resumen:
1. Sube esta carpeta a un repositorio de GitHub (se puede hacer arrastrando los archivos
   desde la web de GitHub, sin usar comandos de git).
2. Crea un "Web Service" en render.com conectado a ese repositorio.
   - Root directory: `backend`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Render te da un link publico (tipo `https://tu-app.onrender.com`) que funciona desde
   cualquier navegador, incluyendo el celular, sin que tu computador tenga que estar prendido.

## Que hace distinto al Excel

- Sin formulas pegadas como valores estaticos: todo se recalcula en Python cada vez.
- YTD comparable: acumula el presupuesto solo de los meses que ya tienen Real cargado
  (el Excel comparaba el Real acumulado contra el presupuesto de los 12 meses completos,
  lo que mostraba variaciones de -100% a mitad de año).
- Editable en vivo: al escribir un "Real" en la tabla, el backend recalcula toda la
  cascada (Utilidad Bruta, EBITDA, EBIT, EBT, Impuesto, Utilidad Neta, margenes).

## Endpoints

- `GET /api/eerr` — estado de resultados completo.
- `POST /api/eerr/real` — actualiza el Real de una linea/mes. Body: `{"line": "...", "month": "Ago", "value": 12345}`.
- `GET /api/eerr/lineas` — catalogo de lineas disponibles.

## Siguientes pasos si esto se vuelve el modelo "real"

- Mover `data.json` a una base de datos (Postgres/SQLite).
- Agregar autenticacion antes de exponer el POST de actualizacion.
- Tests automatizados sobre `engine.py` (ya es 100% funcion pura, facil de testear).
