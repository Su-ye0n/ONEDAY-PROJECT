"""
P2 - 개인 소비 변화 분석 모듈

고객·월·대분류별 지출을 만들고, 이번 달을
  (1) 전월
  (2) 직전 3개월 평균
과 비교해 급증/급감/신규 카테고리를 찾아 문구로 만든다.

입력 df 조건: 중복·취소가 제거된 거래 (P1 loader.load_clean 결과)
              + classify.add_categories 로 붙인 big_category 컬럼
"""
from __future__ import annotations

import pandas as pd

from classify import BIG_CATEGORY_ORDER

# 급증·급감 판정 기준: 비율과 금액을 둘 다 넘어야 한다.
# 비율만 보면 3천 원 → 6천 원(+100%) 같은 소액 변화가 잡히고,
# 금액만 보면 원래 큰 카테고리의 자연스러운 흔들림이 잡히기 때문.
PCT_THRESHOLD = 0.30      # ±30%
WON_THRESHOLD = 30_000    # ±3만 원
HISTORY_MONTHS = 3        # 비교 기준: 직전 3개월 평균
MAX_MESSAGES = 3          # 리포트에 보여줄 문구 최대 개수


# ---------------------------------------------------------------------------
# 공통 유틸
# ---------------------------------------------------------------------------
def ensure_ym(df: pd.DataFrame) -> pd.DataFrame:
    """ym(YYYY-MM) 컬럼이 없으면 transaction_datetime에서 만든다."""
    if "ym" in df.columns:
        return df
    out = df.copy()
    out["ym"] = pd.to_datetime(out["transaction_datetime"]).dt.strftime("%Y-%m")
    return out


def won(n: float) -> str:
    """금액을 '15만 2천 원' 형식으로 표시"""
    n = int(round(abs(n)))
    if n < 10_000:
        return f"{n:,}원"
    man, rest = divmod(n, 10_000)
    chun = rest // 1_000
    return f"{man:,}만 {chun}천 원" if chun else f"{man:,}만 원"


# ---------------------------------------------------------------------------
# 1. 월별 집계
# ---------------------------------------------------------------------------
def monthly_spend(df: pd.DataFrame) -> pd.DataFrame:
    """
    고객 × 월 × 대분류 지출표 (long 형식).
    지출이 없는 달도 0으로 채운다. 0을 채우지 않으면 '전월'이 실제 전월이 아니라
    마지막으로 쓴 달이 되어 증감률이 틀어진다.
    """
    df = ensure_ym(df)
    agg = (df.groupby(["customer_id", "ym", "big_category"])
             .agg(amount=("amount", "sum"), tx_count=("amount", "size"))
             .reset_index())

    grid = pd.MultiIndex.from_product(
        [df["customer_id"].unique(), sorted(df["ym"].unique()), BIG_CATEGORY_ORDER],
        names=["customer_id", "ym", "big_category"],
    ).to_frame(index=False)

    full = grid.merge(agg, how="left", on=["customer_id", "ym", "big_category"])
    full[["amount", "tx_count"]] = full[["amount", "tx_count"]].fillna(0).astype("int64")
    return full.sort_values(["customer_id", "big_category", "ym"]).reset_index(drop=True)


# ---------------------------------------------------------------------------
# 2. 증감 계산
# ---------------------------------------------------------------------------
def add_change_columns(monthly: pd.DataFrame) -> pd.DataFrame:
    """전월 금액, 직전 3개월 평균, 증감액·증감률, 상태를 붙인다."""
    m = monthly.sort_values(["customer_id", "big_category", "ym"]).copy()
    g = m.groupby(["customer_id", "big_category"])["amount"]

    m["prev_amount"] = g.shift(1)
    # shift(1) 후 rolling → 이번 달을 제외한 '직전' 3개월 평균
    m["avg_3m"] = g.transform(
        lambda s: s.shift(1).rolling(HISTORY_MONTHS, min_periods=1).mean()
    )
    m["history_months"] = g.cumcount().clip(upper=HISTORY_MONTHS)

    m["diff_prev"] = m["amount"] - m["prev_amount"]
    m["diff_3m"] = m["amount"] - m["avg_3m"]
    m["pct_prev"] = m["diff_prev"] / m["prev_amount"].where(m["prev_amount"] > 0)
    m["pct_3m"] = m["diff_3m"] / m["avg_3m"].where(m["avg_3m"] > 0)

    m["status"] = "유지"
    new = (m["avg_3m"] == 0) & (m["amount"] >= WON_THRESHOLD)
    spike = (m["pct_3m"] >= PCT_THRESHOLD) & (m["diff_3m"] >= WON_THRESHOLD)
    drop = (m["pct_3m"] <= -PCT_THRESHOLD) & (m["diff_3m"] <= -WON_THRESHOLD)
    m.loc[spike, "status"] = "급증"
    m.loc[drop, "status"] = "급감"
    m.loc[new, "status"] = "신규"
    m.loc[m["history_months"] == 0, "status"] = "기준없음"   # 첫 달은 비교 불가
    return m.reset_index(drop=True)


def change_table(df: pd.DataFrame, customer_id: str, month: str) -> pd.DataFrame:
    """한 고객·한 달의 대분류별 변화표"""
    chg = add_change_columns(monthly_spend(df[df["customer_id"] == customer_id]))
    out = chg[chg["ym"] == month].copy()
    out["big_category"] = pd.Categorical(out["big_category"], BIG_CATEGORY_ORDER, ordered=True)
    return out.sort_values("big_category").reset_index(drop=True)


# ---------------------------------------------------------------------------
# 3. 문구 생성
# ---------------------------------------------------------------------------
def _message(row: pd.Series) -> str:
    cat = row["big_category"]
    if row["status"] == "신규":
        return f"이번 달 {cat}에 {won(row['amount'])}을 새로 썼어요."
    pct = abs(row["pct_3m"]) * 100
    if row["status"] == "급증":
        return (f"이번 달 {cat} 지출이 최근 3개월 평균보다 {pct:.0f}% 늘었어요 "
                f"(+{won(row['diff_3m'])}).")
    return (f"이번 달 {cat} 지출이 최근 3개월 평균보다 {pct:.0f}% 줄었어요 "
            f"(-{won(row['diff_3m'])}). 잘하고 있어요!")


# ---------------------------------------------------------------------------
# 4. 공통 인터페이스 (report.py가 호출)
# ---------------------------------------------------------------------------
def analyze(df: pd.DataFrame, customer_id: str, month: str) -> dict:
    tbl = change_table(df, customer_id, month)
    if tbl.empty:
        return {"feature": "change", "title": "소비 변화",
                "message": f"{month} 거래 내역이 없어요.", "data": {}}

    total_now = int(tbl["amount"].sum())
    total_avg = float(tbl["avg_3m"].sum())

    flagged = tbl[tbl["status"].isin(["급증", "신규", "급감"])].copy()
    # 절대 증감액이 큰 순서로 문구 우선순위를 정한다
    flagged["impact"] = flagged["diff_3m"].abs()
    flagged = flagged.sort_values("impact", ascending=False)
    messages = [_message(r) for _, r in flagged.head(MAX_MESSAGES).iterrows()]

    if total_avg > 0:
        total_pct = (total_now - total_avg) / total_avg * 100
        headline = (f"이번 달 총 {won(total_now)} 썼어요. 최근 3개월 평균보다 "
                    f"{abs(total_pct):.0f}% {'많아요' if total_pct >= 0 else '적어요'}.")
    else:
        headline = f"이번 달 총 {won(total_now)} 썼어요."

    cols = ["big_category", "amount", "prev_amount", "avg_3m",
            "diff_3m", "pct_3m", "status"]
    return {
        "feature": "change",
        "title": "소비 변화",
        "message": messages[0] if messages else headline,
        "data": {
            "headline": headline,
            "messages": messages,
            "total_amount": total_now,
            "total_avg_3m": round(total_avg),
            "table": tbl[cols].astype({"big_category": str}).to_dict("records"),
        },
    }