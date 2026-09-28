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

def analyze(df: pd.DataFrame, customer_id: str, month: str) -> dict:
    return {
        "feature": "installment",
        "title": "다음 달 예정 지출",
        "message": "",
        "data": {}
    }