import pandas as pd



def get_installment_transactions(df: pd.DataFrame) -> pd.DataFrame:
    if "installment_months" not in df.columns:
        raise ValueError("installment_months 컬럼이 필요합니다.")

    installment_df = df[
        (df["transaction_status"] == "APPROVED") &
        (df["installment_months"] > 0)
    ].copy()

    return installment_df


def add_monthly_payment(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    result["monthly_payment"] = (
        result["amount"] / result["installment_months"]
    )

    return result

def calculate_remaining_installment(
    df: pd.DataFrame,
    month: str
) -> pd.DataFrame:

    result = df.copy()

    # 거래일시를 datetime으로 변환
    result["transaction_datetime"] = pd.to_datetime(
        result["transaction_datetime"]
    )

    # 분석 기준월
    target_month = pd.Period(month, freq="M")

    # 거래 발생 월
    result["purchase_month"] = (
        result["transaction_datetime"].dt.to_period("M")
    )

    # 기준월 이후에 발생한 미래 거래는 제외
    result = result[
        result["purchase_month"] <= target_month
    ].copy()

    # 거래 발생 월을 1회차 납부월로 가정
    result["paid_months"] = (
        (target_month.year - result["purchase_month"].dt.year) * 12
        + (target_month.month - result["purchase_month"].dt.month)
        + 1
    )

    # 납부 회차가 0보다 작거나
    # 전체 할부 개월 수를 넘지 않도록 보정
    result["paid_months"] = result["paid_months"].clip(
        lower=0
    )

    result["paid_months"] = result[
        ["paid_months", "installment_months"]
    ].min(axis=1)

    # 남은 회차
    result["remaining_months"] = (
        result["installment_months"]
        - result["paid_months"]
    )

    # 남은 할부금
    result["remaining_amount"] = (
        result["monthly_payment"]
        * result["remaining_months"]
    )

    return result

def calculate_next_month_payment(
    df: pd.DataFrame
) -> pd.DataFrame:

    result = df.copy()

    result["next_month_payment"] = 0.0

    mask = result["remaining_months"] > 0

    result.loc[
        mask,
        "next_month_payment"
    ] = result.loc[
        mask,
        "monthly_payment"
    ]

    return result

def summarize_next_month_by_customer(
    df: pd.DataFrame
) -> pd.DataFrame:

    summary = (
        df.groupby("customer_id", as_index=False)
        .agg(
            next_month_installment=("next_month_payment", "sum"),
            remaining_installment_amount=("remaining_amount", "sum"),
            installment_count=("transaction_id", "count")
        )
    )

    return summary

def installment_status(df: pd.DataFrame, month: str) -> pd.DataFrame:
    """위 4단계를 한 번에 실행한다: 할부 거래 → 월 납입액 → 남은 회차·금액 → 다음 달 납입액"""
    result = get_installment_transactions(df)
    result = add_monthly_payment(result)
    result = calculate_remaining_installment(result, month)
    result = calculate_next_month_payment(result)
    return result


def _won(n: float) -> str:
    """금액을 '15만 2천 원' 형식으로 표시"""
    n = int(round(abs(n)))
    if n < 10_000:
        return f"{n:,}원"
    man, rest = divmod(n, 10_000)
    chun = rest // 1_000
    return f"{man:,}만 {chun}천 원" if chun else f"{man:,}만 원"


def analyze(df: pd.DataFrame, customer_id: str, month: str) -> dict:
    """
    공통 인터페이스 (report.py가 호출).
    month 기준으로 다음 달 할부 납입 예정액과 남은 할부금을 알려준다.
    """
    next_month = str(pd.Period(month, freq="M") + 1)

    if "installment_months" not in df.columns:
        return {"feature": "installment", "title": "다음 달 예정 지출",
                "message": "할부 정보가 없는 데이터예요.", "data": {}}

    status = installment_status(df[df["customer_id"] == customer_id], month)
    active = status[status["remaining_months"] > 0].copy()

    if active.empty:
        return {"feature": "installment", "title": "다음 달 예정 지출",
                "message": f"{next_month[5:].lstrip('0')}월에 나갈 할부금이 없어요.",
                "data": {"next_month": next_month, "next_month_installment": 0,
                         "remaining_installment_amount": 0, "installments": []}}

    next_total = int(round(active["next_month_payment"].sum()))
    remaining_total = int(round(active["remaining_amount"].sum()))
    ending = active[active["remaining_months"] == 1]

    message = (f"{next_month[5:].lstrip('0')}월 할부 납입액은 {_won(next_total)}이에요. "
               f"남은 할부금은 {len(active)}건, 총 {_won(remaining_total)}이에요.")
    if not ending.empty:
        message += f" 그중 {len(ending)}건은 다음 달에 끝나요."

    cols = ["transaction_datetime", "merchant_name", "amount", "installment_months",
            "monthly_payment", "paid_months", "remaining_months", "remaining_amount"]
    items = active.sort_values("remaining_months")[cols].copy()
    items["transaction_datetime"] = items["transaction_datetime"].dt.strftime("%Y-%m-%d")
    items["monthly_payment"] = items["monthly_payment"].round().astype(int)
    items["remaining_amount"] = items["remaining_amount"].round().astype(int)

    return {
        "feature": "installment",
        "title": "다음 달 예정 지출",
        "message": message,
        "data": {
            "next_month": next_month,
            "next_month_installment": next_total,
            "remaining_installment_amount": remaining_total,
            "ending_next_month": int(len(ending)),
            "installments": items.to_dict("records"),
        },
    }