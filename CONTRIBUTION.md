# 팀원별 기여 내역

`git shortlog -sne --all` / `git log --name-only` 기준으로 정리했습니다 (숫자는 이 저장소에 실제로 찍힌 커밋 수).

| 담당 | 이름 | GitHub 계정 | 주요 파일 | 커밋 수 |
|---|---|---|---|---|
| P1 | 우지예 | WJYEE / wjyee | `src/loader.py`, `report.py`, PR 머지 | 12 (+ 이번 세션 AI 보완, 아래 참고) |
| P2 | 조수연 | Su-ye0n | `src/classify.py`, `src/change.py`, `sql/queries_P2.sql`, `notebooks/change_P2.ipynb` | 15 |
| P3 | 구재현 | koojaehyeon4859-cell | `src/forecast.py`, `sql/queries_P3.sql`, `notebooks/forecast_P3.ipynb` | 2 |
| P4 | 정우준 | wjddnwns0111-max | `notebooks/cohort_P4.ipynb` | 2 |
| P5 | 강미 | 121rkdal-ops | `src/recurring.py`, `sql/queries_P5.sql`, `notebooks/recurring_P5.ipynb` | 2 |
| P6 | 권지은 | zsilver1253 | `src/installment.py`, `sql/queries_P6.sql`, `notebooks/installment_P6.ipynb` | 4 |
| P7 | 허준 | hjun4420 | `src/card_tracker.py`, `sql/queries_P7.sql` | 2 |

## 파트별 Pull Request / 링 리뷰

각자 fork → feature 브랜치 → upstream `dev`로 PR을 보냈습니다 (`git log --merges` 기준 PR #3~#19). 링 리뷰(다음 번호 담당자가 리뷰) 기록은 각 PR의 GitHub 코멘트를 참고하세요.

## 특이사항 — P4, P6, P7

- **P4(정우준)**: 실제 커밋은 `notebooks/cohort_P4.ipynb`뿐이었고, 리포트가 호출하는 `src/cohort.py`는 최초 스캐폴딩 이후 한 번도 작성되지 않았습니다(0바이트). `sql/queries_P4.sql`도 비어 있었습니다. **이번 세션에서 Claude(AI)의 도움을 받아 P1이 `src/cohort.py`와 `sql/queries_P4.sql`을 작성**했습니다 — 노트북에 이미 있던 3단계 코호트 완화 로직과 SQL 교차검증 셀 스펙을 그대로 구현한 것입니다. 상세 내역은 [ai_log.md](ai_log.md) 참고.
- **P6(권지은)**: `src/installment.py` 로직은 완성. `notebooks/installment_P6.ipynb`는 저장소에 없는 `data/transactions_with_installment_clean.csv`를 읽게 되어 있어 그대로는 실행이 안 되지만, 이제 `data/installment_months_only.csv`가 채워지고 `loader.py`가 자동으로 붙여주기 때문에 `loader.load_clean()` 결과를 쓰도록 노트북 첫 셀만 고치면 바로 실행됩니다. `src/installment.py` vs `sql/queries_P6.sql`은 실제 데이터 1,808건으로 교차검증 완료(불일치 0건).
- **P7(허준)**: `data/card_benefits.csv`는 이제 채워졌지만, 이 파일로부터 카드 실적을 계산하는 노트북(`notebooks/card_P7.ipynb`)이 저장소에 없습니다. 미리 계산해 둔 `results/pandas/p7_card_alerts_2025-12.csv` 결과만으로 동작해서, 12월 외 다른 달은 카드 실적 카드만 나오지 않습니다.

## 체크리스트 (각자 본인 행에 표시)

| 담당 | 본인 이름 파일 main 포함 | Commit 2회 이상 | PR 1개 이상 머지 | 링 리뷰 1회 | SQL·Pandas 일치 확인 | ai_log 1건 |
|---|---|---|---|---|---|---|
| P1 |  |  |  |  |  |  |
| P2 |  |  |  |  |  |  |
| P3 |  |  |  |  |  |  |
| P4 |  |  |  |  |  |  |
| P5 |  |  |  |  |  |  |
| P6 |  |  |  |  |  |  |
| P7 |  |  |  |  |  |  |
