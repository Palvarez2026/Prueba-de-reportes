"""
API + frontend del EERR - Mina RA (servicio unico)
Local:   uvicorn main:app --reload --port 8000  ->  http://localhost:8000
Render:  uvicorn main:app --host 0.0.0.0 --port $PORT
"""

from pathlib import Path
from typing import Optional

from fastapi import Cookie, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

import auth
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

STATIC_DIR = Path(__file__).parent / "static"


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
    disparos_des: Optional[float] = None
    disparos_banco: Optional[float] = None
    ton_bruta: Optional[float] = None
    ton_selec: Optional[float] = None
    concentrado: Optional[float] = None
    mtrs_banco: Optional[float] = None
    anfo: Optional[float] = None
    detonadores: Optional[float] = None
    combustible: Optional[float] = None
    horas_equipos: Optional[float] = None
    personal: Optional[float] = None
    disp_equipo: Optional[float] = None
    novedades: Optional[str] = None


class LoginRequest(BaseModel):
    rol: str
    clave: str


class PasswordChangeRequest(BaseModel):
    rol: str
    nueva_clave: str


# --------------------------------------------------------------------------
# Autenticacion / sesion
# --------------------------------------------------------------------------

def current_role(session: Optional[str] = Cookie(default=None)) -> Optional[str]:
    return auth.verify_token(session)


def require_role(rol_actual: Optional[str], permitidos: list[str]):
    if rol_actual is None:
        raise HTTPException(status_code=401, detail="No autenticado. Inicia sesión en /login.html")
    if rol_actual not in permitidos:
        raise HTTPException(status_code=403, detail="Tu rol no tiene acceso a esta información")


@app.post("/api/login")
def login(body: LoginRequest, response: Response):
    if not auth.check_login(body.rol, body.clave):
        raise HTTPException(status_code=401, detail="Rol o clave incorrectos")
    token = auth.make_token(body.rol)
    response.set_cookie(
        "session", token, httponly=True, samesite="lax", max_age=auth.SESSION_MAX_AGE,
    )
    return {"rol": body.rol, "landing": auth.DEFAULT_LANDING[body.rol]}


@app.post("/api/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


@app.get("/api/me")
def me(session: Optional[str] = Cookie(default=None)):
    rol = auth.verify_token(session)
    if not rol:
        return {"autenticado": False}
    return {
        "autenticado": True,
        "rol": rol,
        "landing": auth.DEFAULT_LANDING[rol],
        "paginas_permitidas": [p for p, roles in auth.PAGE_ACCESS.items() if rol in roles],
    }


@app.post("/api/admin/password")
def admin_set_password(body: PasswordChangeRequest, session: Optional[str] = Cookie(default=None)):
    rol_actual = auth.verify_token(session)
    require_role(rol_actual, ["admin"])
    try:
        auth.set_password(body.rol, body.nueva_clave)
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True}


# --------------------------------------------------------------------------
# API de datos (protegida por rol)
# --------------------------------------------------------------------------

@app.get("/api/eerr")
def get_eerr(session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "director"])
    state = engine.load_state()
    return engine.compute_eerr(state)


@app.get("/api/eerr/lineas")
def get_lineas(session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "director"])
    state = engine.load_state()
    return {k: v["label"] for k, v in state["detail_lines"].items()}


@app.post("/api/eerr/real")
def post_real(update: RealUpdate, session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "director"])
    state = engine.load_state()
    try:
        engine.update_real(state, update.line, update.month, update.value)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    engine.save_state(state)
    return engine.compute_eerr(state)


@app.get("/api/ingreso-diario")
def get_ingreso_diario(desde: Optional[str] = None, hasta: Optional[str] = None,
                        session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "supervisor"])
    return daily.get_range(desde, hasta)


@app.post("/api/ingreso-diario")
def post_ingreso_diario(entry: DailyEntry, session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "supervisor"])
    fields = entry.model_dump(exclude={"fecha"}, exclude_none=True)
    try:
        rec = daily.upsert_day(entry.fecha, fields)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"fecha": entry.fecha, **rec}


@app.get("/api/resumen-diario")
def get_resumen_diario(fecha: str, session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "director"])
    try:
        return daily.compute_resumen(fecha)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo calcular el resumen: {e}")


@app.get("/api/gantt")
def get_gantt(session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "director"])
    state = gantt.load_state()
    return gantt.compute_gantt(state)


@app.post("/api/gantt/tarea")
def post_gantt_tarea(tarea: GanttTarea, session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "director"])
    state = gantt.load_state()
    try:
        gantt.upsert_tarea(state, tarea.model_dump(exclude_none=False))
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    gantt.save_state(state)
    return gantt.compute_gantt(state)


@app.delete("/api/gantt/tarea/{tarea_id}")
def delete_gantt_tarea(tarea_id: str, session: Optional[str] = Cookie(default=None)):
    require_role(auth.verify_token(session), ["admin", "director"])
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


# --------------------------------------------------------------------------
# Paginas (html) - servidas a mano para poder filtrar por rol antes de
# entregar el archivo (en vez del StaticFiles mount anterior, que servia
# cualquier pagina a cualquiera).
# --------------------------------------------------------------------------

@app.get("/login.html")
def serve_login():
    return FileResponse(STATIC_DIR / "login.html")


@app.get("/")
def root(session: Optional[str] = Cookie(default=None)):
    rol = auth.verify_token(session)
    if not rol:
        return RedirectResponse("/login.html")
    return RedirectResponse(auth.DEFAULT_LANDING[rol])


@app.get("/{page_name}")
def serve_page(page_name: str, session: Optional[str] = Cookie(default=None)):
    if page_name not in auth.PAGE_ACCESS:
        raise HTTPException(status_code=404, detail="No encontrado")
    rol = auth.verify_token(session)
    if rol is None:
        return RedirectResponse("/login.html")
    if rol not in auth.PAGE_ACCESS[page_name]:
        # no tiene acceso a esta pagina puntual -> lo mandamos a la suya, no a un error crudo
        return RedirectResponse(auth.DEFAULT_LANDING[rol])
    return FileResponse(STATIC_DIR / page_name)
