"""
Registro diario de operaciones (Ingreso Diario) y Resumen Diario - Mina RA.
Complementa a engine.py (que maneja el EERR mensual) con el detalle dia a dia
que cargan los operadores en terreno.
"""

import json
import calendar
from datetime import date as date_cls, timedelta
from pathlib import Path

import engine

DAILY_PATH = Path(__file__).parent / "ingreso_diario.json"

MONTH_MAP = {6: "Jun", 7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic"}

FIELD_LABELS = {
    "disparos_des": "Disparos Desarrollo (N°)",
    "disparos_banco": "Disparos Banco (N°)",
    "ton_bruta": "Ton Bruta (ton)",
    "ton_selec": "Ton Seleccionado (ton)",
    "concentrado": "Concentrado (ton)",
    "mtrs_banco": "Metros Perforados Banco",
    "anfo": "ANFO consumido (kg)",
    "detonadores": "Detonadores (unid)",
    "combustible": "Combustible (L)",
    "horas_equipos": "Horas Equipos",
    "personal": "Personal Presente",
    "disp_equipo": "Disponibilidad Equipos",
}

# campo -> linea del EERR (kpi_lines) que tiene el presupuesto mensual
BUDGET_FIELDS = {
    "disparos_banco": "disparos_bancos",
    "ton_bruta": "produccion_bruta",
    "ton_selec": "mineral_seleccionado",
    "concentrado": "concentrado",
}

# campos sin presupuesto asociado (solo se registra el real)
NO_BUDGET_FIELDS = ["disparos_des", "mtrs_banco", "anfo", "detonadores",
                    "combustible", "horas_equipos", "personal", "disp_equipo"]

# campos que se promedian en vez de sumar al acumular varios dias
AVG_FIELDS = {"personal", "disp_equipo"}

ALL_FIELDS = list(BUDGET_FIELDS.keys()) + NO_BUDGET_FIELDS


def load_daily():
    if not DAILY_PATH.exists():
        return {}
    with open(DAILY_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_daily(data):
    with open(DAILY_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def upsert_day(date_str, fields):
    if _parse(date_str) > date_cls.today():
        raise ValueError(f"No se pueden ingresar datos con fecha futura: {date_str}")
    data = load_daily()
    rec = data.get(date_str, {})
    rec.update(fields)
    data[date_str] = rec
    save_daily(data)
    return rec


def _parse(date_str):
    return date_cls.fromisoformat(date_str)


def _aggregate(records, field):
    vals = [r.get(field) for r in records if r.get(field) is not None]
    if not vals:
        return None
    if field in AVG_FIELDS:
        return round(sum(vals) / len(vals), 2)
    return round(sum(vals), 2)


def get_range(desde=None, hasta=None):
    data = load_daily()
    out = {}
    for d, rec in data.items():
        if desde and d < desde:
            continue
        if hasta and d > hasta:
            continue
        out[d] = rec
    return dict(sorted(out.items()))


def compute_resumen(date_str):
    d = _parse(date_str)
    month_key = MONTH_MAP.get(d.month)
    days_in_month = calendar.monthrange(d.year, d.month)[1]
    daily = load_daily()
    today_rec = daily.get(date_str, {})

    month_records = [rec for ds, rec in daily.items()
                      if _parse(ds).year == d.year and _parse(ds).month == d.month and _parse(ds) <= d]

    week_start = d - timedelta(days=d.weekday())
    week_records = [rec for ds, rec in daily.items() if week_start <= _parse(ds) <= d]

    eerr_state = engine.load_state()
    kpi_lines = eerr_state["kpi_lines"]
    detail_lines = eerr_state["detail_lines"]

    def presup_mensual(kpi_key):
        if not month_key:
            return 0
        return kpi_lines[kpi_key]["months"][month_key]["presup"] or 0

    produccion = []
    for field, kpi_key in BUDGET_FIELDS.items():
        presup_mes = presup_mensual(kpi_key)
        presup_dia = round(presup_mes / days_in_month, 2) if days_in_month else 0
        real_dia = today_rec.get(field)
        var = None if real_dia is None else round(real_dia - presup_dia, 2)
        acum_mtd = _aggregate(month_records, field)
        pct_avance = None if not presup_mes or acum_mtd is None else round(acum_mtd / presup_mes, 4)
        produccion.append({
            "campo": field, "label": FIELD_LABELS[field],
            "presup_mes": presup_mes, "presup_dia": presup_dia,
            "real_dia": real_dia, "var": var,
            "acum_mtd": acum_mtd, "pct_avance": pct_avance,
        })

    disparos_des_acum = _aggregate(month_records, "disparos_des")
    produccion.insert(1, {
        "campo": "disparos_des", "label": FIELD_LABELS["disparos_des"],
        "presup_mes": None, "presup_dia": None,
        "real_dia": today_rec.get("disparos_des"), "var": None,
        "acum_mtd": disparos_des_acum, "pct_avance": None,
    })

    insumos = []
    for field in ["mtrs_banco", "anfo", "detonadores", "combustible", "horas_equipos", "personal", "disp_equipo"]:
        insumos.append({
            "campo": field, "label": FIELD_LABELS[field],
            "real_dia": today_rec.get(field),
            "acum_mtd": _aggregate(month_records, field),
        })

    ingreso_presup_mes = None
    if month_key:
        ingreso_presup_mes = detail_lines["venta_concentrado"]["months"][month_key]["presup"]
    ingreso_presup_dia = round(ingreso_presup_mes / days_in_month, 2) if ingreso_presup_mes and days_in_month else None

    ton_bruta_mtd = _aggregate(month_records, "ton_bruta") or 0
    ton_bruta_presup_mes = presup_mensual("produccion_bruta")
    concentrado_mtd = _aggregate(month_records, "concentrado") or 0
    concentrado_presup_mes = presup_mensual("concentrado")

    ton_bruta_semana = _aggregate(week_records, "ton_bruta") or 0
    ton_bruta_presup_semana = round(ton_bruta_presup_mes / days_in_month * 7, 2) if days_in_month else 0
    concentrado_semana = _aggregate(week_records, "concentrado") or 0
    concentrado_presup_semana = round(concentrado_presup_mes / days_in_month * 7, 2) if days_in_month else 0

    return {
        "fecha": date_str,
        "mes": month_key,
        "dia_semana": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][d.weekday()],
        "dias_transcurridos": d.day,
        "dias_totales_mes": days_in_month,
        "avance_temporal": round(d.day / days_in_month, 4) if days_in_month else None,
        "produccion": produccion,
        "insumos": insumos,
        "financiero": {
            "ingreso_presup_mes": ingreso_presup_mes,
            "ingreso_presup_dia": ingreso_presup_dia,
        },
        "avance_mes": {
            "ton_bruta_mtd": ton_bruta_mtd, "ton_bruta_presup_mes": ton_bruta_presup_mes,
            "ton_bruta_pct": round(ton_bruta_mtd / ton_bruta_presup_mes, 4) if ton_bruta_presup_mes else None,
            "concentrado_mtd": concentrado_mtd, "concentrado_presup_mes": concentrado_presup_mes,
            "concentrado_pct": round(concentrado_mtd / concentrado_presup_mes, 4) if concentrado_presup_mes else None,
        },
        "avance_semana": {
            "ton_bruta_semana": ton_bruta_semana, "ton_bruta_presup_semana": ton_bruta_presup_semana,
            "ton_bruta_pct": round(ton_bruta_semana / ton_bruta_presup_semana, 4) if ton_bruta_presup_semana else None,
            "concentrado_semana": concentrado_semana, "concentrado_presup_semana": concentrado_presup_semana,
            "concentrado_pct": round(concentrado_semana / concentrado_presup_semana, 4) if concentrado_presup_semana else None,
        },
        "novedades": today_rec.get("novedades"),
    }
