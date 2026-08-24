"""
Motor de calculo del Estado de Resultados (EERR) - Mina RA
Reemplaza la logica de formulas de Excel por funciones Python puras y testeables.
"""

import json
from pathlib import Path

MONTHS = ["Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
DATA_PATH = Path(__file__).parent / "data.json"


def load_state():
    with open(DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_state(state):
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def _variance(real, presup):
    if real is None:
        return {"presup": presup, "real": None, "var": None, "var_pct": None}
    var = round(real - presup, 2)
    var_pct = None if presup == 0 else round(var / presup, 4)
    return {"presup": presup, "real": round(real, 2), "var": var, "var_pct": var_pct}


def _sum_category(detail_lines, category, month):
    presup_total = 0
    real_total = 0
    real_has_data = False
    for line in detail_lines.values():
        if line["category"] != category:
            continue
        m = line["months"][month]
        presup_total += m["presup"] or 0
        if m["real"] is not None:
            real_has_data = True
            real_total += m["real"]
    return presup_total, (real_total if real_has_data else None)


def compute_eerr(state):
    detail_lines = state["detail_lines"]
    tax_rate = state["tax_rate"]

    result = {"months": {}, "detail_lines": {}}

    for key, line in detail_lines.items():
        result["detail_lines"][key] = {
            "label": line["label"],
            "category": line["category"],
            "months": {m: _variance(line["months"][m]["real"], line["months"][m]["presup"]) for m in MONTHS},
        }

    for month in MONTHS:
        ingresos_p, ingresos_r = _sum_category(detail_lines, "ingreso", month)
        costos_mina_p, costos_mina_r = _sum_category(detail_lines, "costo_mina", month)
        planta_oh_p, planta_oh_r = _sum_category(detail_lines, "planta_oh", month)
        da_p, da_r = _sum_category(detail_lines, "da", month)
        fin_p, fin_r = _sum_category(detail_lines, "financiero", month)

        util_bruta_p = ingresos_p - costos_mina_p
        util_bruta_r = None if (ingresos_r is None or costos_mina_r is None) else ingresos_r - costos_mina_r

        ebitda_p = util_bruta_p - planta_oh_p
        ebitda_r = None if (util_bruta_r is None or planta_oh_r is None) else util_bruta_r - planta_oh_r

        ebit_p = ebitda_p - da_p
        ebit_r = None if (ebitda_r is None or da_r is None) else ebitda_r - da_r

        ebt_p = ebit_p - fin_p
        ebt_r = None if (ebit_r is None or fin_r is None) else ebit_r - fin_r

        impuesto_p = round(ebt_p * tax_rate, 2)
        impuesto_r = None if ebt_r is None else round(ebt_r * tax_rate, 2)

        util_neta_p = ebt_p - impuesto_p
        util_neta_r = None if (ebt_r is None or impuesto_r is None) else ebt_r - impuesto_r

        margen_ebitda_r = None if (ebitda_r is None or not ingresos_r) else round(ebitda_r / ingresos_r, 4)
        margen_ebit_r = None if (ebit_r is None or not ingresos_r) else round(ebit_r / ingresos_r, 4)
        margen_neto_r = None if (util_neta_r is None or not ingresos_r) else round(util_neta_r / ingresos_r, 4)

        result["months"][month] = {
            "total_ingresos": _variance(ingresos_r, ingresos_p),
            "total_costos_mina": _variance(costos_mina_r, costos_mina_p),
            "utilidad_bruta": _variance(util_bruta_r, util_bruta_p),
            "total_planta_overhead": _variance(planta_oh_r, planta_oh_p),
            "ebitda": _variance(ebitda_r, ebitda_p),
            "da_participacion": _variance(da_r, da_p),
            "ebit": _variance(ebit_r, ebit_p),
            "gastos_financieros": _variance(fin_r, fin_p),
            "ebt": _variance(ebt_r, ebt_p),
            "impuesto": _variance(impuesto_r, impuesto_p),
            "utilidad_neta": _variance(util_neta_r, util_neta_p),
            "margenes": {
                "ebitda_pct": margen_ebitda_r,
                "ebit_pct": margen_ebit_r,
                "neto_pct": margen_neto_r,
            },
        }

    closed_months = [m for m in MONTHS if result["months"][m]["utilidad_neta"]["real"] is not None]
    result["closed_months"] = closed_months

    ytd_fields = ["total_ingresos", "total_costos_mina", "utilidad_bruta", "total_planta_overhead",
                  "ebitda", "da_participacion", "ebit", "gastos_financieros", "ebt", "impuesto", "utilidad_neta"]

    ytd = {}
    for field in ytd_fields:
        presup_sum = sum(result["months"][m][field]["presup"] for m in closed_months) if closed_months else 0
        if closed_months:
            reales = [result["months"][m][field]["real"] for m in closed_months]
            real_sum = None if any(r is None for r in reales) else sum(reales)
        else:
            real_sum = None
        ytd[field] = _variance(real_sum, presup_sum)
    result["ytd"] = ytd

    result["presupuesto_anual"] = {
        field: sum(result["months"][m][field]["presup"] for m in MONTHS) for field in ytd_fields
    }

    result["kpi_lines"] = state["kpi_lines"]
    result["meta"] = state["meta"]
    return result


def update_real(state, line_key, month, value):
    if line_key not in state["detail_lines"]:
        raise KeyError(f"Linea desconocida: {line_key}")
    if month not in MONTHS:
        raise KeyError(f"Mes desconocido: {month}")
    state["detail_lines"][line_key]["months"][month]["real"] = value
    return state
