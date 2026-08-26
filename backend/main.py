"""
API + frontend del EERR - Mina RA (servicio unico)
Local:   uvicorn main:app --reload --port 8000  ->  http://localhost:8000
Render:  uvicorn main:app --host 0.0.0.0 --port $PORT
"""

from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import engine
import daily
import gantt

app = FastAPI(title="EERR Mina RA API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RealUpdate(BaseModel):
    line: str
    month: str
    value: float | None = None


class GanttTarea(BaseModel):
    id: Optional[str] = None
    actividad: Optional[str] = None
    fecha_inicio_plan: Optional[str] = None
    duracion_plan: Optional[int] = None
    fecha_inicio_real: Optional[str] = None
    duracion_real: Optional[int] = None
    responsable: Optional[str] = None
    criticidad: Optional[str] = None
    comentario: Optional[str] = None
    porcentaje: Optional[float] = None


class DailyEntry(BaseModel):
    fecha: str
    disparos_np: Optional[float] = None
    disparos_des: Optional[float] = None
    disparos_banco: Optional[float] = None
    ton_bruta: Optional[float] = None
    ton_selec: Optional[float] = None
    concentrado: Optional[float] = None
    mtrs_np: Optional[float] = None
    mtrs_banco: Optional[float] = None
    anfo: Optional[float] = None
    detonadores: Optional[float] = None
    combustible: Optional[float] = None
    horas_equipos: Optional[float] = None
    personal: Optional[float] = None
    disp_equipo: Optional[float] = None
    novedades: Optional[str] = None


@app.get("/api/eerr")
def get_eerr():
    state = engine.load_state()
    return engine.compute_eerr(state)


@app.get("/api/eerr/lineas")
def get_lineas():
    state = engine.load_state()
    return {k: v["label"] for k, v in state["detail_lines"].items()}


@app.post("/api/eerr/real")
def post_real(update: RealUpdate):
    state = engine.load_state()
    try:
        engine.update_real(state, update.line, update.month, update.value)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    engine.save_state(state)
    return engine.compute_eerr(state)


@app.get("/api/ingreso-diario")
def get_ingreso_diario(desde: Optional[str] = None, hasta: Optional[str] = None):
    return daily.get_range(desde, hasta)


@app.post("/api/ingreso-diario")
def post_ingreso_diario(entry: DailyEntry):
    fields = entry.model_dump(exclude={"fecha"}, exclude_none=True)
    try:
        rec = daily.upsert_day(entry.fecha, fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"fecha": entry.fecha, **rec}


@app.get("/api/resumen-diario")
def get_resumen_diario(fecha: str):
    try:
        return daily.compute_resumen(fecha)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo calcular el resumen: {e}")


@app.get("/api/gantt")
def get_gantt():
    state = gantt.load_state()
    return gantt.compute_gantt(state)


@app.post("/api/gantt/tarea")
def post_gantt_tarea(tarea: GanttTarea):
    state = gantt.load_state()
    try:
        gantt.upsert_tarea(state, tarea.model_dump(exclude_none=False))
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    gantt.save_state(state)
    return gantt.compute_gantt(state)


@app.delete("/api/gantt/tarea/{tarea_id}")
def delete_gantt_tarea(tarea_id: str):
    state = gantt.load_state()
    try:
        gantt.delete_tarea(state, tarea_id)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    gantt.save_state(state)
    return gantt.compute_gantt(state)


@app.get("/api/health")
def health():
    return {"status": "ok"}


STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
