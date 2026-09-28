"""
P3 - 지출 예측

1. 이번 달 말 예상 지출 : (현재까지 변동지출 ÷ 경과 일수 × 해당 월 일수) + 고정비
2. 다음 달 대분류별 예측 : 기본 모델 SMA(최근 3개월 단순 이동평균)
                          개선 모델 WMA(최근 3개월 가중 이동평균, 가중치 1:2:3)
3. 백테스트             : 직전 3개월로 예측한 값과 실제값의 MAE 비교

입력 df: loader.load_clean() 결과 (ym, dt, big_category, category_std 컬럼 필요)
'이번 달 진행 중' 상황은 load_clean(as_of="2025-12-20")처럼 기준일까지 자른 데이터로 만든다.
"""
from __future__ import annotations

import calendar

import numpy as np
import pandas as pd

WINDOW = 3
WMA_WEIGHTS = np.array([1, 2, 3]) / 6          # 오래된 달 → 최근 달
FIXED_CATEGORIES = ["SUBSCRIPTION"]            # P5 정기결제 연동 전 임시 고정비 기준
# 최종 모델: 전체 고객 백테스트(4~12월)에서 SMA MAE가 WMA보다 작아 SMA를 채택 (노트북 참고)
FINAL_MODEL = "sma"


def _won(n: float) -> str:
    n = int(round(abs(n)))
    if n < 10_000:
        return f"{n:,}원"
    man, rest = divmod(n, 10_000)
    chun = rest // 1_000
    return f"{man:,}만 {chun}천 원" if chun else f"{man:,}만 원"


def _shift_month(month: str, k: int) -> str:
    return str(pd.Period(month, freq="M") + k)


def _cat_col(df: pd.DataFrame) -> str:
    return "big_category" if "big_category" in df.columns else "category_std"


def _approved(df: pd.DataFrame) -> pd.DataFrame:
    if "transaction_status" in df.columns:
        return df[df["transaction_status"] == "APPROVED"]
    return df


# ---------------------------------------------------------------------------
# 1. 이번 달 말 예상 지출
# ---------------------------------------------------------------------------
def calculate_current_month_forecast(df_user: pd.DataFrame, current_month: str,
                                     fixed_costs: int = 0) -> dict:
    """
    경과 일수 = 데이터에 있는 이번 달 마지막 거래일.
    (load_clean(as_of=...)로 자른 데이터면 기준일까지의 페이스가 된다)
    고정비는 월초에 몰려 있어 페이스 계산에 넣으면 과대추정되므로 빼고 계산한 뒤 따로 더한다.
    """
    df_user = _approved(df_user)
    month_df = df_user[df_user["ym"] == current_month]
    prev_total = int(df_user[df_user["ym"] == _shift_month(current_month, -1)]["amount"].sum())

    p = pd.Period(current_month, freq="M")
    days_in_month = calendar.monthrange(p.year, p.month)[1]

    if month_df.empty:
        return {"actual_to_date": 0, "elapsed_days": 0, "days_in_month": days_in_month,
                "projected_total": 0, "prev_month_total": prev_total,
                "diff_from_last_month": -prev_total,
                "message": f"{p.month}월 거래 내역이 아직 없어요."}

    actual = int(month_df["amount"].sum())
    elapsed = int(pd.to_datetime(month_df["transaction_datetime"]).max().day)
    variable = max(actual - fixed_costs, 0)
    projected = int(round(variable / elapsed * days_in_month + fixed_costs))
    diff = projected - prev_total

    if elapsed >= days_in_month:
        message = f"{p.month}월에 총 {_won(actual)} 썼어요."
    else:
        message = f"이 속도면 {p.month}월에 {_won(projected)}을 쓰게 돼요."
    if prev_total > 0:
        message += f" 지난달보다 {_won(diff)} {'많아요' if diff >= 0 else '적어요'}."

    return {"actual_to_date": actual, "elapsed_days": elapsed, "days_in_month": days_in_month,
            "projected_total": projected, "prev_month_total": prev_total,
            "diff_from_last_month": diff, "message": message}


# ---------------------------------------------------------------------------
# 2. 다음 달 대분류별 예측
# ---------------------------------------------------------------------------
def predict_next_month_categories(df_user: pd.DataFrame, target_month: str = "2026-01") -> dict:
    """target_month 직전 3개월로 target_month의 대분류별 지출을 예측한다."""
    past_3m = [_shift_month(target_month, -i) for i in range(WINDOW, 0, -1)]
    df_3m = _approved(df_user)
    df_3m = df_3m[df_3m["ym"].isin(past_3m)]

    if df_3m.empty:
        empty = pd.Series(dtype=float)
        return {"past_3m_used": past_3m, "sma_series": empty, "wma_series": empty,
                "sma_forecast": {}, "wma_forecast": {},
                "top_category": None, "top_category_amount": 0}

    pivot = (df_3m.pivot_table(index="ym", columns=_cat_col(df_3m), values="amount", aggfunc="sum")
                  .reindex(past_3m).fillna(0))           # 거래 없는 달은 0

    sma = pivot.mean(axis=0)
    wma = pivot.apply(lambda col: float(np.dot(col.values, WMA_WEIGHTS)), axis=0)

    return {
        "past_3m_used": past_3m,
        "sma_series": sma,
        "wma_series": wma,
        "sma_forecast": sma.round().astype(int).to_dict(),
        "wma_forecast": wma.round().astype(int).to_dict(),
        "top_category": (sma if FINAL_MODEL == "sma" else wma).idxmax(),
        "top_category_amount": int(round((sma if FINAL_MODEL == "sma" else wma).max())),
    }


# ---------------------------------------------------------------------------
# 3. 백테스트
# ---------------------------------------------------------------------------
def run_backtest(df_user: pd.DataFrame, test_month: str = "2025-12") -> dict:
    """test_month 이전 데이터만으로 test_month를 예측하고 실제값과 MAE를 비교한다 (고객 1명)."""
    df_user = _approved(df_user)
    col = _cat_col(df_user)
    actual = df_user[df_user["ym"] == test_month].groupby(col)["amount"].sum()
    pred = predict_next_month_categories(df_user[df_user["ym"] < test_month], test_month)

    if actual.empty or pred["sma_series"].empty:
        return {"mae_sma": None, "mae_wma": None, "selected_model": "SMA (데이터 부족)",
                "improvement": "N/A"}

    cats = actual.index.union(pred["sma_series"].index)
    y = actual.reindex(cats, fill_value=0)
    mae_sma = float(np.mean(np.abs(y - pred["sma_series"].reindex(cats, fill_value=0))))
    mae_wma = float(np.mean(np.abs(y - pred["wma_series"].reindex(cats, fill_value=0))))

    if mae_wma < mae_sma:
        selected = "WMA (가중 이동평균)"
        improvement = f"SMA 대비 오차 {round((mae_sma - mae_wma) / mae_sma * 100, 1)}% 감소"
    else:
        selected = "SMA (단순 이동평균)"
        improvement = "기본 모델 채택"
    return {"mae_sma": round(mae_sma), "mae_wma": round(mae_wma),
            "selected_model": selected, "improvement": improvement}


def backtest_all(df: pd.DataFrame, months: list[str]) -> pd.DataFrame:
    """
    전체 고객 × 대분류 × 대상 월에 대해 SMA/WMA 예측과 실제값을 만든다 (노트북·SQL 교차검증용).
    지출이 없는 달은 0으로 채운 뒤 계산한다.
    """
    df = _approved(df)
    col = _cat_col(df)
    all_months = sorted(df["ym"].unique())
    grid = (df.groupby(["customer_id", "ym", col])["amount"].sum()
              .unstack("ym").reindex(columns=all_months).fillna(0))
    rows = []
    for m in months:
        prev = [_shift_month(m, -i) for i in range(WINDOW, 0, -1)]
        if not set(prev + [m]) <= set(all_months):
            continue
        hist = grid[prev].to_numpy()
        rows.append(pd.DataFrame({
            "customer_id": grid.index.get_level_values(0),
            "category": grid.index.get_level_values(1),
            "ym": m,
            "actual": grid[m].to_numpy(),
            "sma": hist.mean(axis=1),
            "wma": hist @ WMA_WEIGHTS,
        }))
    out = pd.concat(rows, ignore_index=True)
    out["err_sma"] = (out["actual"] - out["sma"]).abs()
    out["err_wma"] = (out["actual"] - out["wma"]).abs()
    return out


# ---------------------------------------------------------------------------
# 4. 공통 인터페이스 (report.py가 호출)
# ---------------------------------------------------------------------------
def analyze(df: pd.DataFrame, customer_id: str, month: str) -> dict:
    df_user = df[df["customer_id"] == customer_id]

    cur = df_user[(df_user["ym"] == month) & (df_user["category_std"].isin(FIXED_CATEGORIES))]
    fixed_costs = int(cur["amount"].sum()) if not cur.empty else 0

    res_now = calculate_current_month_forecast(df_user, current_month=month, fixed_costs=fixed_costs)
    next_month = _shift_month(month, 1)
    # 이번 달이 아직 진행 중이면(기준일 데이터) 이번 달은 금액이 덜 쌓여 있으므로
    # 다 끝난 직전 3개월로 예측한다.
    month_done = res_now["elapsed_days"] >= res_now["days_in_month"]
    if month_done:
        res_next = predict_next_month_categories(df_user, target_month=next_month)
    else:
        res_next = predict_next_month_categories(df_user[df_user["ym"] < month], target_month=month)
    res_bt = run_backtest(df_user, test_month=month)

    message = res_now["message"]
    if res_next["top_category"]:
        message += (f" 다음 달에는 {res_next['top_category']}에 "
                    f"{_won(res_next['top_category_amount'])} 정도 쓸 것으로 보여요.")

    return {
        "feature": "forecast",
        "title": "지출 예측",
        "message": message,
        "data": {
            "projected_total": res_now["projected_total"],
            "elapsed_days": res_now["elapsed_days"],
            "diff_from_last_month": res_now["diff_from_last_month"],
            "next_month": next_month,
            "next_month_basis": res_next["past_3m_used"],
            "next_month_top_category": res_next["top_category"],
            "next_month_top_amount": res_next["top_category_amount"],
            "sma_forecast_by_cat": res_next["sma_forecast"],
            "wma_forecast_by_cat": res_next["wma_forecast"],
            "backtest": res_bt,
        },
    }


if __name__ == "__main__":
    # 레포 최상위에서: python src/forecast.py
    from loader import load_clean
    full = load_clean()
    print(analyze(full, "C0003", "2025-12")["message"])
    mid = load_clean(as_of="2025-12-20")
    print(analyze(mid, "C0003", "2025-12")["message"])