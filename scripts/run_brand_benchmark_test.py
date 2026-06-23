"""Prueba del benchmark asesor vs promedio de marca."""

import json
import sys

from app.services.deal_analytics.advisor_benchmark_query import AdvisorBrandBenchmarkService


def main() -> int:
    data = AdvisorBrandBenchmarkService().benchmark(only_registered=True, tolerance_pct=10.0)

    print("=== RESUMEN ===")
    print(json.dumps(data["summary"], ensure_ascii=False, indent=2))
    print("generated_at:", data["generated_at"])
    print("brands:", ", ".join(data["brands"]))
    print()

    if data["unmatched_registrations"]:
        print("=== NO ENCONTRADOS EN HUBSPOT ===")
        for item in data["unmatched_registrations"]:
            print(
                f"  - {item.get('registered_name')} ({item.get('brand_label')}) "
                f"-> {item.get('location')}"
            )
        print()

    if data["advisors_missing_email"]:
        print("=== SIN CORREO ===")
        for item in data["advisors_missing_email"]:
            print(f"  - {item.get('owner_name')} ({item.get('brand_label')})")
        print()

    print("=== ASESORES ===")
    for row in data["advisors"]:
        action = row["action"]
        if action == "felicitar":
            icon = "OK"
        elif action == "compromiso_mejora":
            icon = "MEJORA"
        else:
            icon = "SIN DATOS"
        areas = ", ".join(row["improvement_areas"][:3]) if row["improvement_areas"] else "-"
        strengths = ", ".join(row["strengths"][:3]) if row["strengths"] else "-"
        print(f"[{icon}] {row['owner_name']} - {row['brand_label']} - {row['email']}")
        print(
            f"     accion={action} | encima={row['metrics_above_count']} "
            f"similar={row['metrics_similar_count']} debajo={row['metrics_below_count']}"
        )
        print(f"     fortalezas: {strengths}")
        print(f"     mejorar: {areas}")
        print()

    out_path = "scripts/brand_benchmark_test_result.json"
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    print(f"JSON completo guardado en: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
