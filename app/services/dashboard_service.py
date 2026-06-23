"""Servicio de agregación para el dashboard semanal gerencial."""

from __future__ import annotations

import statistics
from datetime import UTC, date, datetime, timedelta
from typing import Any

from app.config import get_settings
from app.repositories.dashboard_repository import DashboardRepository
from app.schemas.dashboard import (
    AdvisorActivityRow,
    BrandResultRow,
    CloseRateChart,
    Contacted24hBrandRow,
    DashboardCharts,
    DashboardFiltersApplied,
    DashboardFiltersResponse,
    DashboardKpiCard,
    DashboardMetadata,
    DashboardWeeklyResponse,
    DataQualityRuleRow,
    FilterOption,
    FirstResponseBrandRow,
    TrendPoint,
)
from app.services.data_quality.brand_inference import infer_contact_brand
from app.services.hubspot_configuration import get_hubspot_config
from app.utils.dates import parse_hubspot_datetime, utc_now
from app.utils.week_bounds import (
    bogota_now,
    in_range,
    monday_of,
    parse_week_start,
    recent_week_starts,
    week_bounds,
    week_starts_between,
)


DQ_DISPLAY_RULES: tuple[tuple[str, str, str], ...] = (
    ("DEAL_WITHOUT_OWNER", "Sin propietario", "critical"),
    ("DEAL_WITHOUT_CONTACT", "Sin contacto asociado", "critical"),
    ("DEAL_WITH_UNKNOWN_PIPELINE", "Pipeline desconocido", "warning"),
    ("DEAL_WITHOUT_AMOUNT", "Sin valor", "info"),
    ("CONTACT_WITHOUT_EMAIL_AND_PHONE", "Sin teléfono ni email", "critical"),
    ("ACTIVITY_WITHOUT_OWNER", "Actividad sin propietario", "info"),
)

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _brand_label(brand: str, config: Any) -> str:
    return config.brand_label(brand)


def _brand_order(config: Any) -> list[str]:
    return [value for value, _ in config.list_brand_filters()]


def _parse_amount(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0



def _deal_brand(deal: dict[str, Any], config: Any) -> str:
    brand, _ = config.resolve_deal_brand(deal)
    return brand


def _parse_deal_amount(deal: dict[str, Any], config: Any) -> float:
    value = config.get_property_value(deal, "deals", "deal_amount")
    if value in (None, ""):
        value = (deal.get("properties") or {}).get("amount")
    return _parse_amount(value)


def _normalize_owner_id(value: Any) -> str | None:
    if value in (None, ""):
        return None
    normalized = str(value).strip()
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    return normalized or None


def _deal_owner(deal: dict[str, Any]) -> str | None:
    props = deal.get("properties") or {}
    return _normalize_owner_id(props.get("hubspot_owner_id"))


def _contact_owner(contact: dict[str, Any]) -> str | None:
    props = contact.get("properties") or {}
    return _normalize_owner_id(props.get("hubspot_owner_id"))


def _deal_pipeline(deal: dict[str, Any]) -> str | None:
    pipeline = deal.get("pipeline_id") or (deal.get("properties") or {}).get("pipeline")
    return str(pipeline) if pipeline not in (None, "") else None


def _is_won(deal: dict[str, Any], config: Any) -> bool:
    return config.is_deal_won(deal)


def _is_lost(deal: dict[str, Any], config: Any) -> bool:
    return config.is_deal_lost(deal)


def _deal_closed_at(deal: dict[str, Any]) -> datetime | None:
    props = deal.get("properties") or {}
    closed = parse_hubspot_datetime(props.get("closedate"))
    if closed:
        return closed
    return parse_hubspot_datetime(deal.get("updated_at_hubspot"))


def _created_at(row: dict[str, Any]) -> datetime | None:
    return parse_hubspot_datetime(row.get("created_at_hubspot"))


def _week_label(week_start: date) -> str:
    end = week_start + timedelta(days=6)
    return f"{week_start.strftime('%d %b')} – {end.strftime('%d %b')}"


def _minutes_between(start: datetime, end: datetime) -> float:
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    return max(0.0, (end - start).total_seconds() / 60.0)


def _format_duration_minutes(minutes: float | None) -> str | None:
    if minutes is None:
        return None
    if minutes < 60:
        return f"{round(minutes)} min"
    hours = minutes / 60
    if hours < 24:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} d"


def _format_cop(amount: float | None) -> str | None:
    if amount is None:
        return None
    abs_val = abs(amount)
    if abs_val >= 1_000_000_000:
        return f"${amount / 1_000_000_000:,.1f} MM".replace(",", "X").replace(".", ",").replace("X", ".")
    if abs_val >= 1_000_000:
        formatted = f"{amount / 1_000_000:,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"${formatted} M"
    if abs_val >= 1_000:
        formatted = f"{amount / 1_000:,.0f}".replace(",", ".")
        return f"${formatted} mil"
    return f"${amount:,.0f}".replace(",", ".")


def _format_cop_full(amount: float) -> str:
    return f"$ {amount:,.0f} COP".replace(",", ".")


def _trend_direction(
    change: float | None,
    direction: str,
) -> str | None:
    if change is None or change == 0:
        return "neutral"
    improved = change > 0 if direction == "higher_is_better" else change < 0
    return "positive" if improved else "negative"


def _build_card(
    *,
    code: str,
    label: str,
    value: float | int | None,
    previous: float | int | None,
    unit: str,
    direction: str,
    data_status: str,
    status_reason: str | None = None,
    display_value: str | None = None,
) -> DashboardKpiCard:
    change_value: float | int | None = None
    change_pct: float | None = None
    if value is not None and previous is not None:
        change_value = value - previous
        if previous != 0:
            change_pct = round((change_value / previous) * 100, 1)
    return DashboardKpiCard(
        code=code,
        label=label,
        value=value,
        unit=unit,
        previous_value=previous,
        change_value=change_value,
        change_percentage=change_pct,
        direction=direction,  # type: ignore[arg-type]
        data_status=data_status,  # type: ignore[arg-type]
        status_reason=status_reason,
        display_value=display_value,
    )


class DashboardService:
    def __init__(self, repository: DashboardRepository | None = None) -> None:
        self._repo = repository or DashboardRepository()
        self._settings = get_settings()
        self._config = get_hubspot_config()

    def get_filters(self) -> DashboardFiltersResponse:
        contacts = self._repo.fetch_all("hubspot_contacts", columns="created_at_hubspot")
        deals = self._repo.fetch_all("hubspot_deals", columns="created_at_hubspot")
        dates: list[date] = []
        for row in contacts + deals:
            ts = _created_at(row)
            if ts:
                dates.append(ts.astimezone(UTC).date())

        if dates:
            earliest = monday_of(min(dates))
            latest = monday_of(max(dates))
            weeks: list[FilterOption] = []
            current = latest
            while current >= earliest:
                weeks.append(
                    FilterOption(value=current.isoformat(), label=_week_label(current))
                )
                current -= timedelta(weeks=1)
        else:
            weeks = [
                FilterOption(value=d.isoformat(), label=_week_label(d))
                for d in recent_week_starts(12)
            ]

        brands = [FilterOption(value="all", label="Todas las marcas")]
        for value, label in self._config.list_brand_filters():
            brands.append(FilterOption(value=value, label=label))

        owners_raw = self._repo.fetch_owners()
        owners = [
            FilterOption(value="all", label="Todos los asesores"),
        ]
        for owner in sorted(owners_raw, key=lambda o: (o.get("last_name") or "", o.get("first_name") or "")):
            if owner.get("archived"):
                continue
            oid = str(owner["hubspot_id"])
            name = " ".join(
                p for p in (owner.get("first_name"), owner.get("last_name")) if p
            ).strip() or f"Asesor {oid}"
            owners.append(FilterOption(value=oid, label=name))

        pipelines_raw = self._repo.fetch_pipelines()
        pipelines = [FilterOption(value="all", label="Todos los pipelines")]
        for pipe in sorted(pipelines_raw, key=lambda p: p.get("label") or ""):
            if pipe.get("archived"):
                continue
            pipelines.append(
                FilterOption(
                    value=str(pipe["pipeline_id"]),
                    label=pipe.get("label") or str(pipe["pipeline_id"]),
                )
            )

        return DashboardFiltersResponse(
            weeks=weeks,
            brands=brands,
            owners=owners,
            pipelines=pipelines,
            metadata={
                "timezone": self._settings.business_timezone,
                "activity_window_days": self._settings.activity_sync_lookback_days,
                "email_tracking_enabled": False,
            },
        )

    def get_weekly_dashboard(
        self,
        *,
        week_start: str | None = None,
        brand: str = "all",
        owner_id: str | None = None,
        pipeline_id: str | None = None,
    ) -> DashboardWeeklyResponse:
        anchor = parse_week_start(week_start) if week_start else monday_of(bogota_now().date())
        start, end = week_bounds(anchor)
        prev_start, prev_end = week_bounds(anchor - timedelta(weeks=1))

        owner_filter = _normalize_owner_id(owner_id) if owner_id and owner_id != "all" else None
        pipeline_filter = pipeline_id if pipeline_id and pipeline_id != "all" else None
        brand_filter = brand if brand and brand != "all" else None
        config = self._config
        brand_order = _brand_order(config)
        amount_mapping_status = config.resolve_property_name("deals", "deal_amount")[1]
        stage_mapping_status = config.resolve_property_name("deals", "deal_stage")[1]

        activity_window_start = datetime(2000, 1, 1, tzinfo=UTC)
        activity_window_days = max(1, (end - activity_window_start).days)
        scope_contact_ids: set[str] = set()
        scope_deal_ids: set[str] = set()
        if owner_filter:
            scope_contact_ids, scope_deal_ids = self._repo.fetch_owner_commercial_scope(
                owner_filter,
                activity_gte=activity_window_start,
                activity_lt=end,
            )

        contacts = self._repo.fetch_all(
            "hubspot_contacts",
            columns="hubspot_id,created_at_hubspot,properties",
        )
        deals = self._repo.fetch_all(
            "hubspot_deals",
            columns="hubspot_id,created_at_hubspot,updated_at_hubspot,pipeline_id,brand,properties",
        )
        contact_brands = self._repo.fetch_contact_deal_brands()
        activity_times = self._repo.fetch_contact_activity_times()
        quality = self._repo.quality_summary()
        owners_map = {
            str(o["hubspot_id"]): " ".join(
                p for p in (o.get("first_name"), o.get("last_name")) if p
            ).strip()
            or f"Asesor {o['hubspot_id']}"
            for o in self._repo.fetch_owners()
        }

        def contact_brand(contact: dict[str, Any]) -> str:
            cid = str(contact["hubspot_id"])
            if cid in contact_brands:
                return contact_brands[cid]
            inferred = infer_contact_brand(contact.get("properties") or {})
            return inferred or "unknown"

        def passes_contact_filters(contact: dict[str, Any]) -> bool:
            if owner_filter:
                cid = str(contact["hubspot_id"])
                if _contact_owner(contact) != owner_filter and cid not in scope_contact_ids:
                    return False
            return not brand_filter or contact_brand(contact) == brand_filter

        def passes_deal_filters(deal: dict[str, Any]) -> bool:
            if owner_filter:
                did = str(deal["hubspot_id"])
                if _deal_owner(deal) != owner_filter and did not in scope_deal_ids:
                    return False
            if pipeline_filter and _deal_pipeline(deal) != pipeline_filter:
                return False
            return not brand_filter or _deal_brand(deal, config) == brand_filter

        filtered_contacts = [c for c in contacts if passes_contact_filters(c)]
        filtered_deals = [d for d in deals if passes_deal_filters(d)]

        def leads_in_range(range_start: datetime, range_end: datetime) -> list[dict[str, Any]]:
            return [
                c
                for c in filtered_contacts
                if in_range(_created_at(c), range_start, range_end)
            ]

        def deals_created_in_range(range_start: datetime, range_end: datetime) -> list[dict[str, Any]]:
            return [
                d
                for d in filtered_deals
                if in_range(_created_at(d), range_start, range_end)
            ]

        def won_in_range(range_start: datetime, range_end: datetime) -> list[dict[str, Any]]:
            result = []
            for deal in filtered_deals:
                if not _is_won(deal, config):
                    continue
                closed = _deal_closed_at(deal)
                if in_range(closed, range_start, range_end):
                    result.append(deal)
            return result

        def lost_in_range(range_start: datetime, range_end: datetime) -> list[dict[str, Any]]:
            result = []
            for deal in filtered_deals:
                if not _is_lost(deal, config):
                    continue
                closed = _deal_closed_at(deal)
                if in_range(closed, range_start, range_end):
                    result.append(deal)
            return result

        week_leads = leads_in_range(start, end)
        prev_leads = leads_in_range(prev_start, prev_end)
        week_deals_created = deals_created_in_range(start, end)
        prev_deals_created = deals_created_in_range(prev_start, prev_end)
        week_won = won_in_range(start, end)
        prev_won = won_in_range(prev_start, prev_end)
        week_lost = lost_in_range(start, end)
        prev_lost = lost_in_range(prev_start, prev_end)

        pipeline_amount = sum(_parse_deal_amount(d, config) for d in week_deals_created)
        prev_pipeline_amount = sum(_parse_deal_amount(d, config) for d in prev_deals_created)

        won_count = len(week_won)
        lost_count = len(week_lost)
        prev_won_count = len(prev_won)
        prev_lost_count = len(prev_lost)

        close_rate: float | None = None
        prev_close_rate: float | None = None
        if won_count + lost_count > 0:
            close_rate = round(won_count / (won_count + lost_count) * 100, 1)
        if prev_won_count + prev_lost_count > 0:
            prev_close_rate = round(prev_won_count / (prev_won_count + prev_lost_count) * 100, 1)

        first_response_values: list[float] = []
        contacted_24h = 0
        eligible_24h = 0
        has_activity_data = bool(activity_times)

        for contact in week_leads:
            cid = str(contact["hubspot_id"])
            created = _created_at(contact)
            if not created:
                continue
            times = sorted(activity_times.get(cid, []))
            if times:
                minutes = _minutes_between(created, times[0])
                first_response_values.append(minutes)
                eligible_24h += 1
                if minutes <= 24 * 60:
                    contacted_24h += 1
            elif has_activity_data:
                eligible_24h += 1

        avg_first_response: float | None = None
        prev_avg_first: float | None = None
        contacted_rate: float | None = None
        prev_contacted_rate: float | None = None

        if first_response_values:
            avg_first_response = round(statistics.mean(first_response_values), 1)

        if eligible_24h > 0 and has_activity_data:
            contacted_rate = round(contacted_24h / eligible_24h * 100, 1)

        prev_leads_for_response = leads_in_range(prev_start, prev_end)
        prev_fr: list[float] = []
        prev_contacted = 0
        prev_eligible = 0
        for contact in prev_leads_for_response:
            cid = str(contact["hubspot_id"])
            created = _created_at(contact)
            if not created:
                continue
            times = sorted(activity_times.get(cid, []))
            if times:
                prev_fr.append(_minutes_between(created, times[0]))
                prev_eligible += 1
                if _minutes_between(created, times[0]) <= 24 * 60:
                    prev_contacted += 1
            elif has_activity_data:
                prev_eligible += 1
        if prev_fr:
            prev_avg_first = round(statistics.mean(prev_fr), 1)
        if prev_eligible > 0 and has_activity_data:
            prev_contacted_rate = round(prev_contacted / prev_eligible * 100, 1)

        activity_status = "available" if has_activity_data else "unavailable"
        activity_reason = (
            None
            if has_activity_data
            else "Sin actividades efectivas sincronizadas en la ventana de 60 días"
        )
        fr_status = activity_status if avg_first_response is not None else (
            "partial" if has_activity_data and week_leads else "unavailable"
        )
        c24_status = activity_status if contacted_rate is not None else (
            "partial" if has_activity_data and week_leads else "unavailable"
        )

        critical_count = quality.get("critical", 0)
        prev_critical = critical_count  # snapshot; sin histórico de calidad

        amount_data_status = "unavailable" if amount_mapping_status == "invalid" else (
            "available" if week_deals_created else "unavailable"
        )
        amount_status_reason = (
            "Mapeo deal_amount inválido o propiedad inexistente en HubSpot"
            if amount_mapping_status == "invalid"
            else (None if week_deals_created else "Sin negocios creados en la semana")
        )
        close_rate_status = "unavailable" if stage_mapping_status == "invalid" else (
            "available" if close_rate is not None else "unavailable"
        )
        close_rate_reason = (
            "Mapeo deal_stage inválido o propiedad inexistente en HubSpot"
            if stage_mapping_status == "invalid"
            else (None if close_rate is not None else "Sin negocios cerrados (ganados o perdidos) en la semana")
        )

        cards = [
            _build_card(
                code="leads_created",
                label="Leads creados",
                value=len(week_leads),
                previous=len(prev_leads),
                unit="count",
                direction="higher_is_better",
                data_status="available",
            ),
            _build_card(
                code="deals_created",
                label="Negocios creados",
                value=len(week_deals_created),
                previous=len(prev_deals_created),
                unit="count",
                direction="higher_is_better",
                data_status="available",
            ),
            _build_card(
                code="pipeline_created_amount",
                label="Pipeline generado",
                value=pipeline_amount if week_deals_created else None,
                previous=prev_pipeline_amount if prev_deals_created else None,
                unit="cop",
                direction="higher_is_better",
                data_status=amount_data_status,  # type: ignore[arg-type]
                status_reason=amount_status_reason,
                display_value=_format_cop(pipeline_amount) if week_deals_created and amount_mapping_status != "invalid" else None,
            ),
            _build_card(
                code="won_deals",
                label="Negocios ganados",
                value=won_count,
                previous=prev_won_count,
                unit="count",
                direction="higher_is_better",
                data_status="available",
            ),
            _build_card(
                code="close_rate",
                label="Tasa de cierre",
                value=close_rate,
                previous=prev_close_rate,
                unit="percent",
                direction="higher_is_better",
                data_status=close_rate_status,  # type: ignore[arg-type]
                status_reason=close_rate_reason,
                display_value=f"{close_rate}%" if close_rate is not None else None,
            ),
            _build_card(
                code="first_response_minutes",
                label="Primera respuesta",
                value=avg_first_response,
                previous=prev_avg_first,
                unit="minutes",
                direction="lower_is_better",
                data_status=fr_status,  # type: ignore[arg-type]
                status_reason=activity_reason,
                display_value=_format_duration_minutes(avg_first_response),
            ),
            _build_card(
                code="contacted_within_24h_rate",
                label="Contactados antes de 24 h",
                value=contacted_rate,
                previous=prev_contacted_rate,
                unit="percent",
                direction="higher_is_better",
                data_status=c24_status,  # type: ignore[arg-type]
                status_reason=activity_reason,
                display_value=f"{contacted_rate}%" if contacted_rate is not None else None,
            ),
            _build_card(
                code="critical_quality_issues",
                label="Hallazgos críticos",
                value=critical_count,
                previous=prev_critical,
                unit="count",
                direction="lower_is_better",
                data_status="available" if quality.get("last_run_at") else "partial",
                status_reason=None
                if quality.get("last_run_at")
                else "Calidad de datos sin ejecución reciente",
            ),
        ]

        history_dates: list[date] = []
        for row in contacts + deals:
            ts = _created_at(row)
            if ts:
                history_dates.append(ts.astimezone(UTC).date())
            closed = _deal_closed_at(row)
            if closed:
                history_dates.append(closed.astimezone(UTC).date())

        if history_dates:
            trend_weeks = week_starts_between(min(history_dates), anchor)
        else:
            trend_weeks = recent_week_starts(8, anchor=anchor)
        leads_and_deals_trend: list[TrendPoint] = []
        pipeline_vs_won: list[TrendPoint] = []
        for ws in trend_weeks:
            ws_start, ws_end = week_bounds(ws)
            wl = leads_in_range(ws_start, ws_end)
            wd = deals_created_in_range(ws_start, ws_end)
            ww = won_in_range(ws_start, ws_end)
            leads_and_deals_trend.append(
                TrendPoint(
                    week_start=ws.isoformat(),
                    week_label=_week_label(ws),
                    leads_created=len(wl),
                    deals_created=len(wd),
                )
            )
            pipeline_vs_won.append(
                TrendPoint(
                    week_start=ws.isoformat(),
                    week_label=_week_label(ws),
                    pipeline_created_amount=sum(_parse_deal_amount(d, config) for d in wd),
                    won_amount=sum(_parse_deal_amount(d, config) for d in ww),
                )
            )

        brand_results: list[BrandResultRow] = []
        leads_with_brand = 0
        for b in brand_order:
            b_leads = [c for c in week_leads if contact_brand(c) == b]
            b_deals = [d for d in week_deals_created if _deal_brand(d, config) == b]
            b_won = [d for d in week_won if _deal_brand(d, config) == b]
            if b != "unknown":
                leads_with_brand += len(b_leads)
            brand_results.append(
                BrandResultRow(
                    brand=b,
                    brand_label=_brand_label(b, config),
                    leads_created=len(b_leads) if week_leads else None,
                    leads_data_status="partial"
                    if week_leads and len(week_leads) > 0 and leads_with_brand < len(week_leads) * 0.7
                    else ("available" if week_leads else "unavailable"),
                    deals_created=len(b_deals),
                    won_deals=len(b_won),
                )
            )

        if week_leads and leads_with_brand < len(week_leads) * 0.5:
            for row in brand_results:
                row.leads_data_status = "unavailable"
                row.leads_created = None

        close_rate_chart = CloseRateChart(
            won_deals=won_count,
            lost_deals=lost_count,
            close_rate=close_rate,
            data_status="available" if won_count + lost_count > 0 else "unavailable",
        )

        advisor_activity_start = activity_window_start if owner_filter else start
        advisor_raw = self._repo.fetch_advisor_activities(start=advisor_activity_start, end=end)
        advisor_rows: list[AdvisorActivityRow] = []
        for entry in advisor_raw:
            oid = _normalize_owner_id(entry.get("owner_id")) or str(entry["owner_id"])
            if owner_filter and oid != owner_filter:
                continue
            calls = entry.get("calls", 0)
            comms = entry.get("communications", 0)
            meetings = entry.get("meetings", 0)
            tasks = entry.get("tasks", 0)
            notes = entry.get("notes", 0)
            advisor_rows.append(
                AdvisorActivityRow(
                    owner_id=oid,
                    owner_name=owners_map.get(oid, f"Asesor {oid}"),
                    calls=calls,
                    communications=comms,
                    completed_meetings=meetings,
                    tasks=tasks,
                    notes=notes,
                    total_effective=calls + comms + meetings,
                )
            )
        advisor_rows.sort(key=lambda r: r.total_effective, reverse=True)

        first_response_by_brand: list[FirstResponseBrandRow] = []
        contacted_by_brand: list[Contacted24hBrandRow] = []
        for b in brand_order:
            b_leads = [c for c in week_leads if contact_brand(c) == b]
            fr_vals: list[float] = []
            c24 = 0
            el24 = 0
            for contact in b_leads:
                cid = str(contact["hubspot_id"])
                created = _created_at(contact)
                if not created:
                    continue
                times = sorted(activity_times.get(cid, []))
                if times:
                    m = _minutes_between(created, times[0])
                    fr_vals.append(m)
                    el24 += 1
                    if m <= 24 * 60:
                        c24 += 1
                elif has_activity_data:
                    el24 += 1
            median_fr = round(statistics.median(fr_vals), 1) if fr_vals else None
            avg_fr = round(statistics.mean(fr_vals), 1) if fr_vals else None
            rate = round(c24 / el24 * 100, 1) if el24 > 0 and has_activity_data else None
            fr_status_b = "unavailable" if not has_activity_data else ("available" if fr_vals else "partial")
            c24_status_b = "unavailable" if not has_activity_data else ("available" if rate is not None else "partial")
            first_response_by_brand.append(
                FirstResponseBrandRow(
                    brand=b,
                    brand_label=_brand_label(b, config),
                    average_first_response_minutes=avg_fr,
                    median_first_response_minutes=median_fr,
                    sample_size=len(fr_vals),
                    data_status=fr_status_b,  # type: ignore[arg-type]
                )
            )
            contacted_by_brand.append(
                Contacted24hBrandRow(
                    brand=b,
                    brand_label=_brand_label(b, config),
                    contacted_within_24h_rate=rate,
                    eligible_contacts=el24,
                    contacted_count=c24,
                    data_status=c24_status_b,  # type: ignore[arg-type]
                )
            )

        by_rule = {item["rule_code"]: item["count"] for item in quality.get("by_rule", [])}
        dq_rows: list[DataQualityRuleRow] = []
        for code, label, severity in DQ_DISPLAY_RULES:
            count = by_rule.get(code, 0)
            if count > 0 or code in by_rule:
                dq_rows.append(
                    DataQualityRuleRow(rule_code=code, label=label, severity=severity, count=count)
                )
        dq_rows.sort(key=lambda r: (SEVERITY_ORDER.get(r.severity, 9), -r.count))

        charts = DashboardCharts(
            leads_and_deals_trend=leads_and_deals_trend,
            brand_results=brand_results,
            pipeline_vs_won=pipeline_vs_won,
            close_rate=close_rate_chart,
            advisor_activities=advisor_rows,
            first_response_by_brand=first_response_by_brand,
            contacted_within_24h_by_brand=contacted_by_brand,
            data_quality=dq_rows,
        )

        return DashboardWeeklyResponse(
            filters=DashboardFiltersApplied(
                week_start=anchor.isoformat(),
                week_end=(anchor + timedelta(days=7)).isoformat(),
                brand=brand_filter or "all",
                owner_id=owner_filter,
                pipeline_id=pipeline_filter,
            ),
            cards=cards,
            charts=charts,
            metadata=DashboardMetadata(
                generated_at=utc_now().isoformat(),
                timezone=self._settings.business_timezone,
                activity_window_days=activity_window_days,
                email_tracking_enabled=False,
                email_data_required=False,
                owner_scope_active=owner_filter is not None,
                owner_scope_note=(
                    "Incluye negocios y contactos gestionados por el asesor "
                    "(vía actividades sincronizadas), además de propietario directo."
                    if owner_filter
                    else None
                ),
                metadata_snapshot_at=config.metadata_snapshot_at,
                metadata_version=config.metadata_version,
                field_mapping_version=config.field_mapping_version,
                dimension_mapping_version=config.dimension_mapping_version,
            ),
        )
