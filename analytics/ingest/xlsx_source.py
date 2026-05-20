from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

from ..contracts import KPIBlock, MonthFacts, MonthMeta, WeekMeta


def _norm(s: Any) -> str:
    t = str(s or "").strip()
    t = t.replace("\u00a0", " ")
    while "  " in t:
        t = t.replace("  ", " ")
    return t


def _norm_l(s: Any) -> str:
    return _norm(s).lower()


def _cell(ws: Any, r: int, c: int) -> str:
    return _norm(ws.cell(r, c).value)


def _row_values(ws: Any, r: int, min_c: int, max_c: int) -> List[str]:
    return [_cell(ws, r, c) for c in range(min_c, max_c + 1)]


def _is_blank_row(vals: List[str]) -> bool:
    return not any(v for v in vals)


def _looks_like_kpi_title(s: str) -> bool:
    t = _norm(s)
    if not t:
        return False
    if len(t) < 4:
        return False
    # "ПОКАЗАТЕЛИ ..." and most KPI blocks are uppercase in the XLS.
    if any(ch.isalpha() for ch in t) and (t.upper() == t):
        return True
    return False


def extract_month_meta(ws: Any, month_label: str) -> MonthMeta:
    # Find the row that contains "Технические данные для расчетов"
    anchor_r: Optional[int] = None
    for r in range(1, 80):
        if "технические данные" in _norm_l(_cell(ws, r, 1)):
            anchor_r = r
            break
    if anchor_r is None:
        raise ValueError("month_meta_anchor_not_found")

    labels = _row_values(ws, anchor_r, 1, 80)
    values = _row_values(ws, anchor_r + 1, 1, 80)

    def idx_of(substr: str) -> Optional[int]:
        for i, lab in enumerate(labels):
            if substr in _norm_l(lab):
                return i
        return None

    i_start = idx_of("начало месяца")
    i_end = idx_of("конец месяца")
    i_days = idx_of("кол-во дней")
    if i_start is None or i_end is None:
        raise ValueError("month_meta_missing_start_end")

    start = values[i_start]
    end = values[i_end]
    days = int(float(values[i_days])) if i_days is not None and values[i_days] else 0

    weeks: List[WeekMeta] = []
    for w in ["i", "ii", "iii", "iv", "v"]:
        i_ws = idx_of(f"{w} неделя начало")
        i_we = idx_of(f"{w} неделя конец")
        i_wd = idx_of(f"{w} неделя дней")
        if i_ws is None or i_we is None:
            continue
        w_start = values[i_ws]
        w_end = values[i_we]
        w_days = int(float(values[i_wd])) if i_wd is not None and values[i_wd] else 0
        weeks.append(WeekMeta(name=w.upper(), start=w_start, end=w_end, days=w_days))

    return MonthMeta(month=month_label, start=start, end=end, days=days, weeks=weeks)


def extract_kpi_blocks(ws: Any) -> List[KPIBlock]:
    max_r = 800
    max_c = 80
    blocks: List[KPIBlock] = []
    r = 1
    while r <= max_r:
        first = _cell(ws, r, 1)
        if _looks_like_kpi_title(first):
            title = first
            header_r: Optional[int] = None
            for rr in range(r + 1, min(r + 12, max_r) + 1):
                if "салон / показатель" in _norm_l(_cell(ws, rr, 1)):
                    header_r = rr
                    break
            if header_r is None:
                r += 1
                continue

            header = _row_values(ws, header_r, 1, max_c)
            while header and not header[-1]:
                header.pop()

            data: List[List[str]] = []
            rr = header_r + 1
            while rr <= max_r:
                vals = _row_values(ws, rr, 1, len(header))
                if _is_blank_row(vals):
                    if data:
                        break
                    rr += 1
                    continue
                if "салон / показатель" in _norm_l(vals[0]):
                    break
                # A new title might begin a new block; stop if we already collected data.
                if _looks_like_kpi_title(vals[0]) and data:
                    break
                data.append(vals)
                rr += 1

            if data:
                blocks.append(KPIBlock(title=title, header=header, rows=data))
                r = rr
                continue
        r += 1
    return blocks


def pick_kpis(blocks: List[KPIBlock]) -> Dict[str, KPIBlock]:
    def score(title: str, needles: List[str]) -> int:
        tl = title.lower()
        return sum(1 for n in needles if n in tl)

    wanted = {
        # The sheet uses "ПОКАЗАТЕЛИ ПРОДАЖ ..." as the revenue block header.
        "revenue": ["выруч", "показатели продаж"],
        "avg_order_check": ["средний чек", "ср чек", "средняя сумма", "чек заказа", "чек на очки"],
        "avg_income_per_client": ["средний доход", "доход от клиента"],
        "conversion": ["конвер"],
    }

    out: Dict[str, KPIBlock] = {}
    for key, needles in wanted.items():
        best: Tuple[int, Optional[KPIBlock]] = (0, None)
        for b in blocks:
            sc = score(b.title, needles)
            if sc > best[0]:
                best = (sc, b)
        if best[1] is not None and best[0] > 0:
            out[key] = best[1]
    return out


@dataclass
class XlsxDashboardSource:
    """
    v1 ingestion source: manual XLSX export from ODL dashboard.
    """

    xlsx_path: str

    def load_month(self, month_label: str) -> MonthFacts:
        # For MVP v1 we read a fixed sheet name pattern.
        wb = openpyxl.load_workbook(self.xlsx_path, data_only=True, read_only=True)
        sheet_name = f"показатели {month_label}"
        if sheet_name not in wb.sheetnames:
            raise ValueError(f"missing_sheet:{sheet_name}")

        ws = wb[sheet_name]
        meta = extract_month_meta(ws, month_label=month_label)
        blocks = extract_kpi_blocks(ws)
        picked = pick_kpis(blocks)

        now = int(time.time())
        return MonthFacts(
            month_meta=meta,
            kpi_blocks_all=blocks,
            kpi_blocks_picked=picked,
            mix_blocks={},
            orders_blocks={},
            people_blocks={},
            source_type="xlsx_manual",
            source_id=self.xlsx_path,
            generated_at_unix=now,
        )

