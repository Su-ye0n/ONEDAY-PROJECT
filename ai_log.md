# AI 사용 기록

각자 AI에 요청한 내용과 채택/수정/폐기 이유를 최소 1건씩 아래에 추가합니다.

## P1 — 우지예

**요청**: 미완성 상태였던 `src/cohort.py`(P4)와 통합 스크립트 `report.py`를 작성해 달라고 Claude에게 요청.

**AI가 한 일**
- `notebooks/cohort_P4.ipynb`에 이미 있던 3단계 코호트 완화 로직(연령×성별×직업×소득구간 → 소득구간 제거 → 직업 제거, 최소 20명)과 SQL 교차검증 셀의 기대 스키마를 그대로 읽어서 `src/cohort.py`와 `sql/queries_P4.sql`을 작성.
- `report.py`가 6개 모듈의 `analyze()`를 순서대로 호출해 카드로 조립하도록 작성. 모듈 하나가 실패해도 나머지 카드는 살아있도록 예외 처리 추가.

**채택/수정/폐기**
- 코호트 로직·SQL은 무작위 고객×월 40건에서 Python·SQL 결과가 100% 일치해 그대로 채택.
- 통합 과정에서 `src/recurring.py`(P5)가 공통 인터페이스(`feature/title/message/data`)를 지키지 않아 `report.py`가 죽는 걸 발견 — AI가 제안한 수정(반환 형식만 맞추고 로직은 그대로 유지)을 그대로 채택.
- AI가 함께 발견한 `installment_months` 컬럼 부재, `data/card_benefits.csv` 빈 파일 문제는 데이터 재생성이 필요한 별도 작업이라 처음에는 README 한계 절에 현황만 기록.
- 이후 P1이 `data/installment_months_only.csv`와 `data/card_benefits.csv`를 직접 채워서 다시 요청 → `src/loader.py`가 `installment_months_only.csv`를 transaction_id 기준으로 자동 병합하도록 수정.
- 이 과정에서 AI가 버그를 하나 더 발견: 병합을 중복 제거보다 먼저 하면, 원래 같은 거래(중복 943건)인데 할부 개월 수만 달라져서 더 이상 중복으로 안 잡히는 문제(927건만 제거됨)가 생김. 중복 판정 키에서 `installment_months`를 제외하도록 수정해 943건으로 복구 — 채택.
- `sql/queries_P6.sql` vs `src/installment.py` 실제 데이터 교차검증(1,808건, 기준월 2025-09)도 이번에 실행해 결과를 README·result_report.md에 반영.

---

## P2 —

**요청**:

**채택/수정/폐기**:

---

## P3 —

**요청**:

**채택/수정/폐기**:

---

## P4 —

**요청**:

**채택/수정/폐기**:

---

## P5 —

**요청**:

**채택/수정/폐기**:

---

## P6 —

**요청**:

**채택/수정/폐기**:

---

## P7 —

**요청**:

**채택/수정/폐기**:
