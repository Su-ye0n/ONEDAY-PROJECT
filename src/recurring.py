import pandas as pd


def _won(n: float) -> str:
    """금액을 '15만 2천 원' 형식으로 표시"""
    n = int(round(abs(n)))
    if n < 10_000:
        return f"{n:,}원"
    man, rest = divmod(n, 10_000)
    chun = rest // 1_000
    return f"{man:,}만 {chun}천 원" if chun else f"{man:,}만 원"


def detect_recurring(df: pd.DataFrame) -> pd.DataFrame:
    """
    전체 거래내역에서 정기결제 후보를 탐지한다.

    탐지 조건
    - 승인된 거래
    - merchant_name 존재
    - 동일 고객 + 동일 가맹점
    - 3개월 이상 반복
    - 동일 금액 반복
    - 결제일 차이 ±3일 범위
    """

    work = df.copy()

    # 승인 거래만 사용
    work = work[work["transaction_status"] == "APPROVED"].copy()

    # 날짜 정보 생성
    work["dt"] = pd.to_datetime(work["transaction_datetime"])
    work["ym"] = work["dt"].dt.to_period("M").astype(str)
    work["day"] = work["dt"].dt.day

    # 가맹점명이 없는 거래는 반복 여부를 판단할 수 없어 제외
    work = work.dropna(subset=["merchant_name"])

    # 고객-가맹점별 반복 패턴 집계
    candidates = (
        work.groupby(["customer_id", "merchant_name"])
        .agg(
            active_months=("ym", "nunique"),
            payment_count=("amount", "size"),
            avg_amount=("amount", "mean"),
            min_amount=("amount", "min"),
            max_amount=("amount", "max"),
            first_date=("dt", "min"),
            last_date=("dt", "max"),
            min_day=("day", "min"),
            max_day=("day", "max"),
        )
        .reset_index()
    )

    # 3개월 이상 반복
    candidates = candidates[
        candidates["active_months"] >= 3
    ].copy()

    # 동일 금액 반복
    candidates = candidates[
        candidates["min_amount"] == candidates["max_amount"]
    ].copy()

    # 결제일 차이 ±3일 범위
    candidates["day_range"] = (
        candidates["max_day"] - candidates["min_day"]
    )

    candidates = candidates[
        candidates["day_range"] <= 6
    ].copy()

    return candidates


def analyze(
    df: pd.DataFrame,
    customer_id: str,
    month: str
) -> dict:
    """
    특정 고객의 정기결제 목록을 반환한다.

    Parameters
    ----------
    df : 전체 거래 데이터
    customer_id : 고객 ID (예: C0003)
    month : 분석 기준 월 (예: 2025-12)
    """

    recurring = detect_recurring(df)

    # 해당 고객의 정기결제 후보
    customer_recurring = recurring[
        recurring["customer_id"] == customer_id
    ].copy()

    # 기준 월에 실제 승인 거래가 있었던 정기결제만 확인
    work = df.copy()
    work = work[work["transaction_status"] == "APPROVED"].copy()
    work["dt"] = pd.to_datetime(work["transaction_datetime"])
    work["ym"] = work["dt"].dt.to_period("M").astype(str)

    month_transactions = work[
        (work["customer_id"] == customer_id)
        & (work["ym"] == month)
    ]

    active_merchants = set(
        month_transactions["merchant_name"].dropna()
    )

    customer_recurring = customer_recurring[
        customer_recurring["merchant_name"].isin(active_merchants)
    ].copy()

    recurring_list = []

    for _, row in customer_recurring.iterrows():
        recurring_list.append(
            {
                "merchant_name": row["merchant_name"],
                "amount": int(row["avg_amount"]),
                "active_months": int(row["active_months"]),
            }
        )

    total_amount = sum(
        item["amount"] for item in recurring_list
    )

    if recurring_list:
        names = ", ".join(item["merchant_name"] for item in recurring_list[:5])
        message = f"매달 나가는 정기결제 {len(recurring_list)}개, 월 {_won(total_amount)}이에요. ({names})"
    else:
        message = f"{month}에는 탐지된 정기결제가 없어요."

    return {
        "feature": "recurring",
        "title": "정기결제",
        "message": message,
        "data": {
            "customer_id": customer_id,
            "month": month,
            "recurring_count": len(recurring_list),
            "recurring_total": total_amount,
            "recurring_list": recurring_list,
        },
    }


if __name__ == "__main__":
    df = pd.read_csv("data/transactions.csv")

    result = analyze(df, "C0003", "2025-12")

    print(result)