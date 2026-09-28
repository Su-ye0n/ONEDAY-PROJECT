"""
P1 - 공통 데이터 로더

모든 파트는 원본 CSV를 직접 읽지 말고 load_clean()을 사용한다.
그래야 파트마다 정제 기준이 달라 통합 리포트 수치가 어긋나는 일이 없다.

정제 규칙
1. 중복 제거: transaction_id만 다르고 나머지 값이 모두 같은 행은 1건만 남긴다 (943건)
2. 취소 제외: transaction_status == 'CANCELLED' (6,403건)
3. 파생 컬럼: dt(datetime), ym('2025-12'), tx_date('2025-12-20'), income_band
4. 카테고리: classify.add_categories() → category_std, big_category, merchant_filled
5. 기준일(as_of): 지정하면 그 날짜까지의 거래만 남긴다 (예: '2025-12-20')

사용 예
    from loader import load_clean
    df = load_clean()                      # 전체 기간
    df = load_clean(as_of="2025-12-20")    # 12/20까지 (카드 실적 등 '이번 달 진행 중' 분석용)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from classify import add_categories

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TRANSACTIONS_PATH = DATA_DIR / "transactions.csv"
CARD_BENEFITS_PATH = DATA_DIR / "card_benefits.csv"

# 팀 공통 기준일. README에도 같은 값을 적는다.
DEFAULT_AS_OF = "2025-12-20"

# P4 코호트용 소득구간 (설계서 5장)
INCOME_BINS = [0, 40_000_000, 60_000_000, float("inf")]
INCOME_LABELS = ["4천만 미만", "4천~6천", "6천 이상"]


def load_raw() -> pd.DataFrame:
    """원본 CSV를 그대로 읽는다 (정제 전 건수 확인용)."""
    if not TRANSACTIONS_PATH.exists():
        raise FileNotFoundError(f"거래 데이터가 없습니다: {TRANSACTIONS_PATH}")
    df = pd.read_csv(TRANSACTIONS_PATH, dtype={"customer_id": str, "transaction_id": str})
    if df.empty:
        raise ValueError(f"거래 데이터 파일이 비어 있습니다: {TRANSACTIONS_PATH}")
    return df


def load_clean(as_of: str | None = None, with_category: bool = True,
               verbose: bool = False) -> pd.DataFrame:
    """
    정제된 거래 데이터를 반환한다.

    as_of         : 'YYYY-MM-DD'. 지정하면 그 날짜(포함)까지의 거래만 남긴다.
    with_category : True면 classify.add_categories()로 카테고리 컬럼을 붙인다.
    verbose       : True면 단계별 건수를 출력한다.
    """
    raw = load_raw()
    n_raw = len(raw)

    # 1) 중복 제거
    key_cols = [c for c in raw.columns if c != "transaction_id"]
    df = raw.drop_duplicates(subset=key_cols, keep="first")
    n_dup = n_raw - len(df)

    # 2) 취소 제외
    df = df[df["transaction_status"] == "APPROVED"].copy()
    n_cancel = n_raw - n_dup - len(df)

    # 3) 파생 컬럼
    df["dt"] = pd.to_datetime(df["transaction_datetime"])
    df["ym"] = df["dt"].dt.strftime("%Y-%m")
    df["tx_date"] = df["dt"].dt.strftime("%Y-%m-%d")
    df["income_band"] = pd.cut(df["annual_income"], bins=INCOME_BINS,
                               labels=INCOME_LABELS, right=False).astype(str)

    # 4) 기준일
    n_after_asof = 0
    if as_of is not None:
        before = len(df)
        df = df[df["tx_date"] <= as_of].copy()
        n_after_asof = before - len(df)

    # 5) 카테고리
    if with_category:
        df = add_categories(df)

    df = df.sort_values(["customer_id", "dt"]).reset_index(drop=True)

    if verbose:
        print(f"원본 {n_raw:,}행 → 중복 {n_dup:,} 제거 → 취소 {n_cancel:,} 제외"
              + (f" → 기준일({as_of}) 이후 {n_after_asof:,} 제외" if as_of else "")
              + f" → {len(df):,}행")
    return df


def load_card_benefits() -> pd.DataFrame:
    """카드 혜택 기준표 (P7용)."""
    if not CARD_BENEFITS_PATH.exists():
        raise FileNotFoundError(f"카드 혜택표가 없습니다: {CARD_BENEFITS_PATH}")
    return pd.read_csv(CARD_BENEFITS_PATH)


if __name__ == "__main__":
    # 레포 최상위에서: python src/loader.py
    full = load_clean(verbose=True)
    print("기간:", full["tx_date"].min(), "~", full["tx_date"].max())
    print("대분류:", full["big_category"].nunique(), "개 / 소득구간:", full["income_band"].value_counts().to_dict())
    load_clean(as_of=DEFAULT_AS_OF, verbose=True)