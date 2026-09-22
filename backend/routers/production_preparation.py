from __future__ import annotations

from collections import defaultdict, deque
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from db.database import get_db
from models.changeovers import Changeover
from models.mould import Mould
from models.moulds_book import MouldsBook
from models.moulds_tpm import CzasReakcji, MouldsTpm, Statusy
from schemas.production_preparation import (
    PreparationAction,
    PreparationChangeover,
    PreparationTpm,
    ProductionPreparationRead,
)


router = APIRouter(prefix="/production-preparation", tags=["production-preparation"])


PRODUCTION_SQL = text(
    """
    SELECT
        row_number() OVER (
            ORDER BY NULLIF(btrim(produkcja_od), '')::timestamp, forma, wyrob, nazwa
        ) AS row_no,
        forma,
        nazwa,
        wyrob,
        typ,
        NULLIF(btrim(produkcja_od), '')::timestamp AS planned_start,
        NULLIF(btrim(produkcja_do), '')::timestamp AS planned_end
    FROM public.produkcja
    WHERE NULLIF(btrim(produkcja_od), '') IS NOT NULL
      AND NULLIF(btrim(produkcja_od), '')::timestamp >= :date_from
      AND NULLIF(btrim(produkcja_od), '')::timestamp < :date_to_exclusive
    ORDER BY planned_start, forma, wyrob
    """
)


def _normalized_mould_number(value: str | None) -> str:
    return (value or "").strip().upper()


def _changeover_graph(changeovers: list[Changeover]) -> dict[int, set[int]]:
    graph: dict[int, set[int]] = defaultdict(set)
    for changeover in changeovers:
        graph[changeover.from_mould_id].add(changeover.to_mould_id)
        graph[changeover.to_mould_id].add(changeover.from_mould_id)
    return graph


def _connected_moulds(start_id: int, graph: dict[int, set[int]]) -> set[int]:
    visited = {start_id}
    queue = deque([start_id])
    while queue:
        mould_id = queue.popleft()
        for neighbour in graph.get(mould_id, set()):
            if neighbour not in visited:
                visited.add(neighbour)
                queue.append(neighbour)
    return visited


def _changeover_timestamp(changeover: Changeover) -> tuple[datetime, int]:
    timestamp = changeover.updated or changeover.created or datetime.min
    return timestamp, changeover.id or 0


def _resolve_changeover(
    required_mould: Mould,
    changeovers: list[Changeover],
    graph: dict[int, set[int]],
    mould_by_id: dict[int, Mould],
) -> tuple[int | None, str | None, bool, PreparationChangeover, list[PreparationAction], list[str]]:
    connected = _connected_moulds(required_mould.id, graph)
    has_changeover_history = any(mould_id != required_mould.id for mould_id in connected)

    if not has_changeover_history:
        return (
            required_mould.id,
            required_mould.mould_number,
            False,
            PreparationChangeover(status="not_required"),
            [],
            [],
        )

    completed = [
        changeover
        for changeover in changeovers
        if changeover.czy_wykonano
        and changeover.from_mould_id in connected
        and changeover.to_mould_id in connected
    ]
    if not completed:
        action = PreparationAction(
            type="confirm_current_version",
            description=f"Potwierdzić aktualną wersję formy przed produkcją {required_mould.mould_number}",
        )
        return (
            None,
            None,
            True,
            PreparationChangeover(status="unknown", to_mould_id=required_mould.id),
            [action],
            ["Brak wykonanego przezbrojenia pozwalającego ustalić aktualną wersję formy"],
        )

    last_completed = max(completed, key=_changeover_timestamp)
    current_mould_id = last_completed.to_mould_id
    current_mould = mould_by_id.get(current_mould_id)
    current_mould_number = current_mould.mould_number if current_mould else str(current_mould_id)

    if current_mould_id == required_mould.id:
        return (
            current_mould_id,
            current_mould_number,
            False,
            PreparationChangeover(
                status="not_required",
                changeover_id=last_completed.id,
                from_mould_id=last_completed.from_mould_id,
                to_mould_id=last_completed.to_mould_id,
            ),
            [],
            [],
        )

    planned = next(
        (
            changeover
            for changeover in sorted(changeovers, key=_changeover_timestamp, reverse=True)
            if not changeover.czy_wykonano
            and changeover.from_mould_id == current_mould_id
            and changeover.to_mould_id == required_mould.id
        ),
        None,
    )

    if planned:
        changeover_info = PreparationChangeover(
            status="planned",
            changeover_id=planned.id,
            from_mould_id=planned.from_mould_id,
            to_mould_id=planned.to_mould_id,
            needed_date=planned.needed_date,
        )
        action = PreparationAction(
            type="changeover",
            record_id=planned.id,
            description=f"Wykonać przezbrojenie {current_mould_number} → {required_mould.mould_number}",
        )
        reason = "Zaplanowane przezbrojenie nie zostało jeszcze wykonane"
    else:
        changeover_info = PreparationChangeover(
            status="missing",
            from_mould_id=current_mould_id,
            to_mould_id=required_mould.id,
        )
        action = PreparationAction(
            type="create_changeover",
            description=f"Zaplanować przezbrojenie {current_mould_number} → {required_mould.mould_number}",
        )
        reason = "Aktualna wersja formy nie odpowiada wersji wymaganej przez produkcję"

    return (
        current_mould_id,
        current_mould_number,
        True,
        changeover_info,
        [action],
        [reason],
    )


def _priority(readiness: str, planned_start: datetime, now: datetime) -> str:
    hours_left = (planned_start - now).total_seconds() / 3600
    if readiness == "blocked" or hours_left <= 24:
        return "critical"
    if readiness != "ready" and hours_left <= 72:
        return "high"
    if readiness != "ready":
        return "medium"
    return "low"


@router.get("/", response_model=list[ProductionPreparationRead])
async def production_preparation_report(
    db: Session = Depends(get_db),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
):
    now = datetime.now()
    report_date_from = date_from or now.date()
    report_date_to = date_to or report_date_from + timedelta(days=2)
    if report_date_to < report_date_from:
        raise HTTPException(
            status_code=400,
            detail="Data 'do' nie może być wcześniejsza niż data 'od'",
        )

    range_start = datetime.combine(report_date_from, time.min)
    range_end_exclusive = datetime.combine(
        report_date_to + timedelta(days=1),
        time.min,
    )
    production_rows = db.execute(
        PRODUCTION_SQL,
        {
            "date_from": range_start,
            "date_to_exclusive": range_end_exclusive,
        },
    ).mappings().all()

    moulds = db.query(Mould).all()
    mould_by_id = {mould.id: mould for mould in moulds}
    mould_by_number = {
        _normalized_mould_number(mould.mould_number): mould
        for mould in moulds
    }

    changeovers = db.query(Changeover).all()
    changeover_by_id = {changeover.id: changeover for changeover in changeovers}
    graph = _changeover_graph(changeovers)

    production_numbers = {
        _normalized_mould_number(row["forma"])
        for row in production_rows
    }
    required_mould_ids = {
        mould_by_number[number].id
        for number in production_numbers
        if number in mould_by_number
    }
    open_statuses = [Statusy.OTWARTY.value, Statusy.W_TRAKCIE_REALIZACJI.value]
    tpm_by_mould_id: dict[int, list[MouldsTpm]] = defaultdict(list)
    if required_mould_ids:
        open_tpms = (
            db.query(MouldsTpm)
            .filter(
                MouldsTpm.mould_id.in_(required_mould_ids),
                MouldsTpm.status.in_(open_statuses),
            )
            .order_by(MouldsTpm.created.asc(), MouldsTpm.id.asc())
            .all()
        )
        for tpm in open_tpms:
            tpm_by_mould_id[tpm.mould_id].append(tpm)

    pre_production_check_dates: dict[int, date] = {}
    if required_mould_ids:
        checked_rows = (
            db.query(
                MouldsBook.mould_id,
                func.max(MouldsBook.created),
            )
            .filter(
                MouldsBook.mould_id.in_(required_mould_ids),
                MouldsBook.tpm_type == 4,
                MouldsBook.opis_zgloszenia.ilike("Sprawdzenie przed produkcją%"),
            )
            .group_by(MouldsBook.mould_id)
            .all()
        )
        pre_production_check_dates = dict(checked_rows)

    report: list[ProductionPreparationRead] = []
    for row in production_rows:
        required_number = (row["forma"] or "").strip()
        required_mould = mould_by_number.get(_normalized_mould_number(required_number))
        production_id = f"production-{row['row_no']}-{required_number or 'unknown'}"

        if not required_mould:
            action = PreparationAction(
                type="fix_production_mould",
                description=f"Uzupełnić lub poprawić numer formy w tabeli produkcja: {required_number or 'brak numeru'}",
            )
            readiness = "blocked"
            report.append(
                ProductionPreparationRead(
                    production_id=production_id,
                    required_mould_number=required_number or "Nieprzypisana",
                    product=row["nazwa"],
                    product_code=row["wyrob"],
                    planned_start=row["planned_start"],
                    planned_end=row["planned_end"],
                    production_type=row["typ"],
                    readiness=readiness,
                    priority=_priority(readiness, row["planned_start"], now),
                    changeover_required=False,
                    changeover=PreparationChangeover(status="unknown"),
                    actions=[action],
                    reasons=["Numer formy z produkcji nie został znaleziony w kartotece moulds"],
                )
            )
            continue

        (
            current_mould_id,
            current_mould_number,
            changeover_required,
            changeover_info,
            actions,
            reasons,
        ) = _resolve_changeover(required_mould, changeovers, graph, mould_by_id)

        latest_pre_production_check = pre_production_check_dates.get(
            required_mould.id
        )
        if latest_pre_production_check is not None and changeover_info.changeover_id:
            completed_changeover = changeover_by_id.get(
                changeover_info.changeover_id
            )
            if (
                completed_changeover is not None
                and latest_pre_production_check
                < _changeover_timestamp(completed_changeover)[0].date()
            ):
                latest_pre_production_check = None

        mould_tpms = tpm_by_mould_id.get(required_mould.id, [])
        tpm_payload = [
            PreparationTpm(
                id=tpm.id,
                status=tpm.status,
                tpm_time_type=tpm.tpm_time_type,
                description=tpm.opis_zgloszenia,
                created=tpm.created,
            )
            for tpm in mould_tpms
        ]
        for tpm in mould_tpms:
            actions.append(
                PreparationAction(
                    type="tpm",
                    record_id=tpm.id,
                    description=tpm.opis_zgloszenia or f"Wykonać TPM #{tpm.id}",
                )
            )

        has_immediate_tpm = any(
            tpm.tpm_time_type == CzasReakcji.NATYCHMIAST.value
            for tpm in mould_tpms
        )
        if has_immediate_tpm:
            readiness = "blocked"
            reasons.append("Otwarty TPM wymaga natychmiastowej reakcji")
        elif changeover_info.status == "unknown":
            readiness = "blocked"
        elif changeover_required:
            readiness = "requires_changeover"
        elif mould_tpms:
            readiness = "requires_tpm"
            reasons.append("Forma ma otwarte TPM-y")
        elif latest_pre_production_check is None:
            readiness = "requires_pre_production_check"
            actions.append(
                PreparationAction(
                    type="pre_production_check",
                    description=(
                        "Wykonać sprawdzenie przed produkcją w Szczegółach formy "
                        f"{required_mould.mould_number}"
                    ),
                )
            )
            reasons.append(
                "Brak wpisu utworzonego przez przycisk „Sprawdzenie przed produkcją”"
            )
        else:
            readiness = "ready"

        report.append(
            ProductionPreparationRead(
                production_id=production_id,
                required_mould_id=required_mould.id,
                required_mould_number=required_mould.mould_number,
                current_mould_id=current_mould_id,
                current_mould_number=current_mould_number,
                product=row["nazwa"] or required_mould.product,
                product_code=row["wyrob"],
                planned_start=row["planned_start"],
                planned_end=row["planned_end"],
                production_type=row["typ"],
                readiness=readiness,
                priority=_priority(readiness, row["planned_start"], now),
                changeover_required=changeover_required,
                changeover=changeover_info,
                open_tpms=tpm_payload,
                actions=actions,
                reasons=reasons,
            )
        )

    return report
