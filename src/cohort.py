"""
P4 - 유사 고객군 비교

코호트 정의: age_group x gender x occupation x income_band.
최소 인원(MIN_PEERS)에 못 미치면 조건을 하나씩 완화한다 (설계서 5장).
  1단계: age_group, gender, occupation, income_band
  2단계: age_group, gender, occupation           (income_band 제거)
  3단계: age_group, gender                       (occupation도 제거)
1단계부터 순서대로 확인해 처음으로 MIN_PEERS 이상이 되는 단계를 채택하고,
3단계에서도 못 채우면 3단계 결과를 인원 수와 함께 그대로 사용한다.

로직: 고객의 이번 달 대분류별 지출 - 코호트 중앙값. 차이(절대값)가 가장 큰
대분류 하나를 대표 문구로 쓴다. 더 쓴 카테고리는 비교 문구, 적게 쓴 카테고리는
칭찬 문구로 표현한다.

sql/queries_P4.sql, notebooks/cohort_P4.ipynb 에서 이 모듈의 Python 결과와
SQL 결과를 교차검증한다.
"""
from __future__ import annotations

import pandas as pd

MIN_PEERS = 20

STAGES: list[tuple[str, ...]] = [
    ("age_group", "gender", "occupation", "income_band"),
    ("age_group", "gender", "occupation"),
    ("age_group", "gender"),
]

GENDER_KO = {"M": "남성", "F": "여성"}
OCCUPATION_KO = {
    "OFFICE_WORKER": "직장인", "SELF_EMPLOYED": "자영업자", "PROFESSIONAL": "전문직",
    "FREELANCER": "프리랜서", "STUDENT": "학생", "HOMEMAKER": "전업주부",
    "PART_TIME": "아르바이트", "MARKETER": "마케터", "RETIRED": "은퇴자",
}


def _won(n: float) -> str:
    """금액을 '15만 2천 원' 형식으로 표시"""
    n = int(round(abs(n)))
    if n < 10_000:
        return f"{n:,}원"
    man, rest = divmod(n, 10_000)
    chun = rest // 1_000
    return f"{man:,}만 {chun}천 원" if chun else f"{man:,}만 원"


def _cat_col(df: pd.DataFrame) -> str:
    return "big_category" if "big_category" in df.columns else "category_std"


def _income_band(income: float) -> str:
    if income < 40_000_000:
        return "4천만 미만"
    if income < 60_000_000:
        return "4천~6천"
    return "6천 이상"


def _describe_cohort(target: pd.Series, stage: int) -> str:
    """1단계 결과를 '30대 남성 직장인'처럼 사람이 읽는 표현으로 만든다."""
    age = str(target["age_group"]).replace("s", "대")
    gender = GENDER_KO.get(target["gender"], target["gender"])
    if stage <= 2:
        occ = OCCUPATION_KO.get(target["occupation"], target["occupation"])
        label = f"{age} {gender} {occ}"
    else:
        label = f"{age} {gender}"
    if stage == 1:
        label += f"({target.get('income_band', '')})"
    return label


def find_cohort(profiles: pd.DataFrame, customer_id: str) -> tuple[int, pd.Index]:
    """
    단계별로 조건을 완화하며 첫 번째로 MIN_PEERS 이상을 만족하는 단계를 찾는다.
    끝까지 못 채우면 마지막 단계(3단계) 결과를 그대로 반환한다.
    profiles: customer_id를 인덱스로 하는 고객 속성 테이블 (age_group, gender,
              occupation, income_band 포함, 이번 달 거래가 있는 고객만).
    """
    if customer_id not in profiles.index:
        return 0, profiles.index[:0]

    target = profiles.loc[customer_id]
    peer_ids = profiles.index[:0]
    for stage, fields in enumerate(STAGES, start=1):
        mask = profiles.index != customer_id
        for field in fields:
            mask &= profiles[field].eq(target[field]).fillna(False)
        peer_ids = profiles.index[mask]
        if len(peer_ids) >= MIN_PEERS:
            return stage, peer_ids
    return len(STAGES), peer_ids


def analyze(df: pd.DataFrame, customer_id: str, month: str) -> dict:
    """
    공통 인터페이스 (report.py가 호출).
    고객의 이번 달 대분류별 지출을 코호트(중앙값)와 비교해 차이가 가장 큰
    대분류 하나를 문구로 만든다.
    """
    col = _cat_col(df)
    work = df[df["transaction_status"] == "APPROVED"] if "transaction_status" in df.columns else df
    month_tx = work[work["ym"] == month]

    if month_tx.empty or customer_id not in set(month_tx["customer_id"]):
        return {"feature": "cohort", "title": "또래 비교",
                "message": f"{month} 거래 내역이 없어 비교할 수 없어요.",
                "data": {"status": "no_data"}}

    profile_cols = ["customer_id", "age_group", "gender", "occupation", "annual_income"]
    profiles = (month_tx[profile_cols].drop_duplicates("customer_id")
                        .set_index("customer_id"))
    profiles["income_band"] = profiles["annual_income"].astype(float).apply(_income_band)

    stage, peer_ids = find_cohort(profiles, customer_id)
    peer_count = int(len(peer_ids))

    if peer_count == 0:
        return {"feature": "cohort", "title": "또래 비교",
                "message": "비교할 또래 고객이 없어요.",
                "data": {"status": "no_peers", "cohort_stage": stage, "peer_count": 0}}

    categories = month_tx[col].dropna().unique()

    peer_tx = month_tx[month_tx["customer_id"].isin(peer_ids)]
    peer_spend = (peer_tx.groupby(["customer_id", col])["amount"].sum()
                         .unstack(col)
                         .reindex(index=peer_ids, columns=categories)
                         .fillna(0.0))

    my_spend = (month_tx[month_tx["customer_id"] == customer_id]
                        .groupby(col)["amount"].sum()
                        .reindex(categories).fillna(0.0))

    table = pd.DataFrame({
        "my_spend": my_spend,
        "peer_mean": peer_spend.mean(axis=0),
        "peer_median": peer_spend.median(axis=0),
    })
    table["diff_from_median"] = table["my_spend"] - table["peer_median"]
    table["abs_diff"] = table["diff_from_median"].abs()
    table = table.sort_values("abs_diff", ascending=False)

    top_category = table.index[0]
    top = table.iloc[0]
    diff = float(top["diff_from_median"])

    cohort_label = _describe_cohort(profiles.loc[customer_id], stage)
    if diff >= 0:
        message = f"비슷한 {cohort_label} 고객보다 {top_category}에 {_won(diff)} 더 썼어요."
    else:
        message = f"비슷한 {cohort_label} 고객보다 {top_category}에 {_won(diff)} 적게 썼어요. 잘하고 있어요!"
    if peer_count < MIN_PEERS:
        message += f" (또래 표본 {peer_count}명, 기준({MIN_PEERS}명)보다 적어 참고용이에요.)"

    return {
        "feature": "cohort",
        "title": "또래 비교",
        "message": message,
        "data": {
            "status": "ok",
            "cohort_stage": int(stage),
            "cohort_label": cohort_label,
            "peer_count": peer_count,
            "category": str(top_category),
            "my_spend": int(round(top["my_spend"])),
            "peer_mean": float(top["peer_mean"]),
            "peer_median": float(top["peer_median"]),
            "diff_from_median": int(round(diff)),
            "table": table.drop(columns="abs_diff").reset_index(names=col).to_dict("records"),
        },
    }


if __name__ == "__main__":
    from loader import load_clean
    full = load_clean()
    print(analyze(full, "C0003", "2025-12")["message"])