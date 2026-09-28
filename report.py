"""
report.py - P1 통합: 여섯 기능의 analyze() 결과를 모아 고객 1명의 월간 리포트로 조립한다.

사용법
    python report.py                   # 기본값: 고객 C0003, 2025-12 (기준일 2025-12-20)
    python report.py C0010 2025-11     # 고객·월 지정 (해당 월이 이미 끝났다면 기준일 없이 전체 데이터 사용)

각 기능 모듈은 4-3절 공통 인터페이스를 따른다:
    def analyze(df, customer_id, month) -> dict
        {"feature": ..., "title": ..., "message": ..., "data": {...}}

한 모듈이 예외를 던지거나(예: P7 사전 계산 결과 파일이 해당 월에 없음) 데이터가
없어도 나머지 카드는 정상적으로 보이도록 카드 단위로 오류를 감싼다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from loader import load_clean, DEFAULT_AS_OF  # noqa: E402
import change  # noqa: E402
import forecast  # noqa: E402
import cohort  # noqa: E402
import recurring  # noqa: E402
import installment  # noqa: E402
import card_tracker  # noqa: E402

# report.py가 호출할 6개 기능 모듈. 순서 = 리포트에 카드가 나타나는 순서.
MODULES = [
    ("change", change, "소비 변화"),
    ("forecast", forecast, "지출 예측"),
    ("cohort", cohort, "또래 비교"),
    ("recurring", recurring, "정기결제"),
    ("installment", installment, "다음 달 예정 지출"),
    ("card_tracker", card_tracker, "카드 실적"),
]


def _safe_analyze(name: str, module, fallback_title: str, df, customer_id: str, month: str) -> dict:
    """모듈 하나가 실패해도 리포트 전체가 죽지 않도록 감싼다 (예: P7 결과 CSV가 해당 월에 없는 경우)."""
    try:
        return module.analyze(df, customer_id, month)
    except Exception as exc:  # noqa: BLE001 - 카드 하나의 실패를 리포트 전체로 번지게 하지 않는다
        return {
            "feature": name,
            "title": fallback_title,
            "message": f"{fallback_title} 카드를 만들지 못했어요. ({exc})",
            "data": {},
            "error": True,
        }


def build_report(customer_id: str, month: str, as_of: str | None = None) -> dict:
    """고객 1명·월 1개의 리포트를 6장의 카드로 조립한다."""
    df = load_clean(as_of=as_of)
    cards = [
        _safe_analyze(name, module, title, df, customer_id, month)
        for name, module, title in MODULES
    ]
    return {"customer_id": customer_id, "month": month, "as_of": as_of, "cards": cards}


def print_report(report: dict) -> None:
    header = f"{report['customer_id']} · {report['month']} 소비 리포트"
    if report["as_of"]:
        header += f" (기준일 {report['as_of']})"
    print("=" * len(header))
    print(header)
    print("=" * len(header))
    for card in report["cards"]:
        mark = "[!] " if card.get("error") else ""
        print(f"\n[{card['title']}]")
        print(f"{mark}{card['message']}")


if __name__ == "__main__":
    # 레포 최상위에서: python report.py [customer_id] [month] [as_of]
    customer_id = sys.argv[1] if len(sys.argv) > 1 else "C0003"
    month = sys.argv[2] if len(sys.argv) > 2 else "2025-12"
    as_of = sys.argv[3] if len(sys.argv) > 3 else (DEFAULT_AS_OF if month == "2025-12" else None)

    report = build_report(customer_id, month, as_of=as_of)
    print_report(report)
