"""
P2 - 카테고리 정제 및 자동 분류 모듈

역할
1. 원본 category 표기 불일치(대소문자, 공백, 오타)를 20종 표준 카테고리로 정규화
2. 표준 카테고리 20종을 사용자 친화적인 대분류(big_category)로 묶기
3. 가맹점명 → 카테고리 사전을 만들어, 카테고리가 없는 거래도 가맹점명만으로 분류
4. merchant_name 결측을 "미상(대분류)"로 채우기

다른 파트(P3, P4, P7)는 add_categories()가 붙여주는
category_std, big_category 컬럼만 사용한다.
"""
from __future__ import annotations

import pandas as pd

# ---------------------------------------------------------------------------
# 1. 표준 카테고리와 오타 교정 사전
# ---------------------------------------------------------------------------
VALID_CATEGORIES = [
    "ACCOMMODATION", "BUSINESS", "CAFE", "CEREMONY", "CONVENIENCE",
    "DELIVERY", "DINING", "EDUCATION", "ENTERTAINMENT", "FASHION",
    "FUEL", "GROCERY", "HOUSEHOLD", "MEDICAL", "ONLINE_SHOPPING",
    "PET", "SUBSCRIPTION", "TRANSPORT", "TRAVEL", "UTILITY",
]

# strip().upper() 이후에도 남는 오타 (데이터에서 직접 확인한 4종)
TYPO_FIX = {
    "DINNING": "DINING",
    "GROCERRY": "GROCERY",
    "DELIVERLY": "DELIVERY",
    "CAFFE": "CAFE",
}

# ---------------------------------------------------------------------------
# 2. 대분류 매핑 (20종 → 12개)
# ---------------------------------------------------------------------------
BIG_CATEGORY = {
    "DINING": "식비",
    "GROCERY": "식비",
    "CONVENIENCE": "식비",
    "CAFE": "카페",
    "DELIVERY": "배달",
    "TRANSPORT": "교통",
    "FUEL": "교통",
    "ONLINE_SHOPPING": "쇼핑",
    "FASHION": "쇼핑",
    "HOUSEHOLD": "쇼핑",
    "SUBSCRIPTION": "구독",
    "UTILITY": "주거통신",
    "MEDICAL": "의료",
    "EDUCATION": "교육",
    "ENTERTAINMENT": "여가",
    "TRAVEL": "여행",
    "ACCOMMODATION": "여행",
    "PET": "기타",
    "BUSINESS": "기타",
    "CEREMONY": "기타",
}
BIG_CATEGORY_ORDER = ["식비", "카페", "배달", "교통", "쇼핑", "구독",
                      "주거통신", "의료", "교육", "여가", "여행", "기타"]


def normalize_category(raw: pd.Series) -> pd.Series:
    """원본 category → 표준 20종. 표준에 없는 값이 남으면 에러를 낸다."""
    std = raw.astype("string").str.strip().str.upper().replace(TYPO_FIX)
    unknown = set(std.dropna().unique()) - set(VALID_CATEGORIES)
    if unknown:
        raise ValueError(f"정규화되지 않은 카테고리가 있습니다: {sorted(unknown)}")
    return std


def to_big_category(category_std: pd.Series) -> pd.Series:
    """표준 카테고리 → 대분류"""
    return category_std.map(BIG_CATEGORY).fillna("기타")


# ---------------------------------------------------------------------------
# 3. 가맹점 사전 (자동 분류의 본체)
# ---------------------------------------------------------------------------
def build_merchant_map(df: pd.DataFrame) -> dict[str, str]:
    """
    가맹점명 → 표준 카테고리 사전.
    한 가맹점이 여러 카테고리로 찍혀 있으면 가장 많이 나온 카테고리(최빈값)를 쓴다.
    df에는 category_std 컬럼이 있어야 한다.
    """
    known = df.dropna(subset=["merchant_name"])
    counts = (known.groupby(["merchant_name", "category_std"]).size()
                   .reset_index(name="n")
                   .sort_values(["merchant_name", "n"], ascending=[True, False]))
    top = counts.drop_duplicates("merchant_name")
    return dict(zip(top["merchant_name"], top["category_std"]))


def classify_merchant(merchant_name: str, merchant_map: dict[str, str]) -> str | None:
    """
    가맹점명만으로 표준 카테고리를 추정한다 (category가 없는 신규 거래용).
    1) 사전에 정확히 있으면 그 값
    2) 사전의 가맹점명이 이름에 포함되어 있으면 그 값 (예: '스타벅스 강남점' → CAFE)
    3) 못 찾으면 None
    """
    if not isinstance(merchant_name, str) or not merchant_name:
        return None
    if merchant_name in merchant_map:
        return merchant_map[merchant_name]
    # 긴 이름부터 비교해야 '코레일KTX'가 '코레일'보다 먼저 잡힌다
    for key in sorted(merchant_map, key=len, reverse=True):
        if key in merchant_name:
            return merchant_map[key]
    return None


# ---------------------------------------------------------------------------
# 4. 파이프라인 진입점
# ---------------------------------------------------------------------------
def add_categories(df: pd.DataFrame) -> pd.DataFrame:
    """
    category_std, big_category, merchant_filled 컬럼을 붙여서 반환한다.
    원본 df는 수정하지 않는다.
    """
    out = df.copy()
    out["category_std"] = normalize_category(out["category"])
    out["big_category"] = to_big_category(out["category_std"])
    out["merchant_filled"] = out["merchant_name"].fillna(
        "미상(" + out["big_category"] + ")"
    )
    return out


def category_report(df: pd.DataFrame) -> pd.DataFrame:
    """원본 표기 → 표준 카테고리 대응표와 건수 (README·검증용)"""
    tmp = pd.DataFrame({
        "category_raw": df["category"],
        "category_std": normalize_category(df["category"]),
    })
    return (tmp.groupby(["category_std", "category_raw"]).size()
               .reset_index(name="rows")
               .sort_values(["category_std", "rows"], ascending=[True, False]))