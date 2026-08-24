"""
Carta Gantt - Minera RA
Logica de lectura/escritura y calculo de estado (a tiempo / atrasada / completada)
para el plan de inicio de proyecto. Reemplaza la carta Gantt de Excel (formato
condicional sobre una grilla de fechas) por tareas con fecha real y % de avance,
expuestas via API REST y editables desde el celular.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

GANTT_PATH = Path(__file__).parent / "gantt.json"


def load_state():
    with open(GANTT_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(GANTT_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _parse(d):
    if not d:
        return None
    return datetime.strptime(d, "%Y-%m-%d").date()


def _add_days(d, n):
    if d is None or n is None:
        return None
    return d + timedelta(days=int(n) - 1)


def _estado(tarea, hoy):
    pct = tarea.get("porcentaje") or 0
    fin_plan = _add_days(_parse(tarea.get("fecha_inicio_plan")), tarea.get("duracion_plan"))
    inicio_real = _parse(tarea.get("fecha_inicio_real"))

    if pct >= 1:
        return "completada"
    if inicio_real is None or inicio_real > hoy:
        return "no_iniciada"
    if fin_plan is not None and hoy > fin_plan:
        return "atrasada"
    return "en_curso"


def compute_gantt(state, hoy=None):
    hoy = hoy or date.today()
    tareas = state["tareas"]

    result_tareas = []
    fechas = []
    for t in tareas:
        inicio_plan = _parse(t.get("fecha_inicio_plan"))
        fin_plan = _add_days(inicio_plan, t.get("duracion_plan"))
        inicio_real = _parse(t.get("fecha_inicio_real"))
        fin_real = _add_days(inicio_real, t.get("duracion_real"))
        for d in (inicio_plan, fin_plan, inicio_real, fin_real):
            if d:
                fechas.append(d)

        result_tareas.append({
            **t,
            "fecha_fin_plan": fin_plan.isoformat() if fin_plan else None,
            "fecha_fin_real": fin_real.isoformat() if fin_real else None,
            "estado": _estado(t, hoy),
        })

    rango_inicio = min(fechas) if fechas else hoy
    rango_fin = max(fechas) if fechas else hoy
    dias_totales = (rango_fin - rango_inicio).days + 1

    total = len(result_tareas)
    completadas = sum(1 for t in result_tareas if t["estado"] == "completada")
    atrasadas = sum(1 for t in result_tareas if t["estado"] == "atrasada")
    en_curso = sum(1 for t in result_tareas if t["estado"] == "en_curso")
    no_iniciadas = sum(1 for t in result_tareas if t["estado"] == "no_iniciada")
    avance_prom = round(sum(t.get("porcentaje") or 0 for t in result_tareas) / total, 4) if total else 0

    return {
        "meta": state["meta"],
        "responsables": state["responsables"],
        "hoy": hoy.isoformat(),
        "rango": {"inicio": rango_inicio.isoformat(), "fin": rango_fin.isoformat(), "dias_totales": dias_totales},
        "resumen": {
            "total": total, "completadas": completadas, "atrasadas": atrasadas,
            "en_curso": en_curso, "no_iniciadas": no_iniciadas, "avance_promedio": avance_prom,
        },
        "tareas": result_tareas,
    }


def upsert_tarea(state, tarea_in):
    tareas = state["tareas"]
    tid = tarea_in.get("id")

    if tid:
        for i, t in enumerate(tareas):
            if t["id"] == tid:
                tareas[i] = {**t, **{k: v for k, v in tarea_in.items() if v is not None or k == "responsable"}}
                return tareas[i]
        raise KeyError(f"Tarea desconocida: {tid}")

    existentes = [int(t["id"].split("-")[1]) for t in tareas if t["id"].startswith("act-")]
    nuevo_num = (max(existentes) + 1) if existentes else 1
    nueva = {
        "id": f"act-{nuevo_num:02d}",
        "actividad": tarea_in.get("actividad", "Nueva actividad"),
        "fecha_inicio_plan": tarea_in.get("fecha_inicio_plan"),
        "duracion_plan": tarea_in.get("duracion_plan"),
        "fecha_inicio_real": tarea_in.get("fecha_inicio_real"),
        "duracion_real": tarea_in.get("duracion_real"),
        "responsable": tarea_in.get("responsable", ""),
        "porcentaje": tarea_in.get("porcentaje", 0.0),
    }
    tareas.append(nueva)
    return nueva


def delete_tarea(state, tid):
    tareas = state["tareas"]
    idx = next((i for i, t in enumerate(tareas) if t["id"] == tid), None)
    if idx is None:
        raise KeyError(f"Tarea desconocida: {tid}")
    tareas.pop(idx)
