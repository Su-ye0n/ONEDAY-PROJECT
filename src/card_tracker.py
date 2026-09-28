"""
P7 - 카드 실적 혜택 트래커

현재 단계: P7이 계산한 결과 파일(results/pandas/p7_card_alerts_<월>.csv)을 읽어
공통 인터페이스 analyze()로 돌려준다.
P7의 계산 코드가 이 파일에 들어오면 load_alerts() 대신 그 함수를 호출하도록 바꾸면 된다.

기준일: 결과는 2025-12-20까지의 거래로 계산됨 (12/21 이후 거래 미포함).
"""
from __future__ import annotations

from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULT_DIR = ROOT / "results" / "pandas"
AS_OF = "2025-12-20"


def load_alerts(month: str) -> pd.DataFrame:
    path = RESULT_DIR / f"p7_card_alerts_{month}.csv"
    if not path.exists():
        raise FileNotFoundError(f"P7 결과 파일이 없습니다: {path}")
    return pd.read_csv(path, dtype={"customer_id": str, "ym": str})


def analyze(df: pd.DataFrame | None, customer_id: str, month: str) -> dict:
    """
    df는 다른 모듈과 인터페이스를 맞추기 위한 인자 (현재는 사용하지 않음).
    대표 알림 카드 선택 기준: '부족액 1원당 되찾는 혜택'(missed_if_short / shortfall)이
    가장 큰 카드. 조금만 더 쓰면 혜택이 커지는 카드를 먼저 알려주기 위해서다.
    되찾을 혜택이 있는 카드가 없으면 부족액이 가장 작은 카드를 고른다.
    """
    alerts = load_alerts(month)
    mine = alerts[alerts["customer_id"] == customer_id].copy()
    if mine.empty:
        return {"feature": "card", "title": "카드 실적",
                "message": f"{month} 카드 실적 정보가 없어요.", "data": {}}

    actionable = mine[mine["message"].notna() & (mine["shortfall"] > 0)]
    actionable = actionable.assign(
        efficiency=actionable["missed_if_short"].fillna(0) / actionable["shortfall"]
    ).sort_values(["efficiency", "shortfall"], ascending=[False, True])
    top = actionable.iloc[0] if not actionable.empty else None

    cols = ["card_product", "card_name", "perf_amount", "achieved_tier",
            "next_threshold", "shortfall", "benefit_this_month",
            "missed_if_short", "message"]
    return {
        "feature": "card",
        "title": "카드 실적",
        "message": top["message"] if top is not None else "모든 카드가 이번 달 실적 구간을 채웠어요.",
        "data": {
            "as_of": AS_OF,
            "benefit_this_month_total": int(mine["benefit_this_month"].sum()),
            "cards": mine[cols].where(mine[cols].notna(), None).to_dict("records"),
        },
    }