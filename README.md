# ONEDAY-PROJECT
<img width="1934" height="698" alt="data_overview" src="https://github.com/user-attachments/assets/2e936971-12a2-4ec5-9069-5f36290527b0" />

**1. transactions.csv (가상 카드 거래 데이터)
**
항목	값
생성 방법	(작성 필요: 예) 생성형 AI로 페르소나 20종 기반 가상 거래 생성)
기간	2025-01-01 ~ 2025-12-31 (12개월)
규모	원본 318,145건 / 정제 후 310,799건
고객	1,000명 (페르소나 20종), 남녀 각 500명
연령	20대 271 · 30대 337 · 40대 226 · 50대 105 · 60대 61명
연봉	818만 ~ 2억 4,000만 원 (중앙값 4,797만 원)
가맹점	147개, 원본 카테고리 20종
결제수단	신용카드 57.4% · 체크카드 33.6% · 계좌이체 9.0%
총 결제액 (정제 후)	약 195억 7,194만 원, 건당 중앙값 22,700원

주요 컬럼: customer_id, age_group, gender, occupation, annual_income, household_type, transaction_datetime, merchant_name, category, amount, payment_method, card_product, transaction_status

**2. 데이터 품질 이슈와 처리 (src/loader.py, src/classify.py)
**
이슈	규모	처리
transaction_id만 다른 중복 행	943건	제거
취소 거래 (CANCELLED)	6,403건	분석에서 제외
카테고리 표기 불일치 (대소문자·공백·오타 DINNING, GROCERRY, DELIVERLY, CAFFE)	64종 → 실제 20종	정규화 후 대분류 12개로 묶음
가맹점명 결측	1,113건	"미상(대분류)"로 표시
card_product 결측	28,321건	모두 계좌이체라 정상 (카드 실적에서만 제외)

모든 분석은 load_clean()으로 같은 기준의 정제 데이터를 사용합니다. 카드 실적처럼 "이번 달 진행 중" 상황이 필요한 분석은 기준일 2025-12-20까지의 거래만 사용합니다 (load_clean(as_of="2025-12-20")).

**3. card_benefits.csv (카드 혜택 기준표)
**
코드	카드명	전월실적 구간
CARD_A	신한카드 Mr.Life	30만 ~ 100만 원
CARD_B	KB국민카드 굿데이카드	30만 ~ 120만 원
CARD_C	하나카드 MOVING카드 ALLDAY모드	실적 조건 없음
CARD_D	삼성카드 삼성 iD SELECT ALL 카드	40만 ~ 120만 원
CARD_E	NH농협카드 올바른 FLEX 카드	30만 원

(작성 필요: 혜택 조건의 출처. 예) 각 카드사 공개 상품설명서를 참고해 단순화. 실제 상품 조건과 다를 수 있음)

**4. 데이터 한계
**
가상 데이터이므로 분석 결과는 실제 소비 행태를 대표하지 않습니다.
2025년 1년치만 있어 전년 동월 비교(계절성)는 할 수 없습니다.
고객별 월 지출 변동이 커서, 소비 급증 판정 기준을 민감도 분석으로 점검했습니다 (notebooks/change_P2.ipynb 7장).
모든 고객이 카드 5장을 모두 사용하도록 생성되어 카드별 실적이 분산됩니다.<img width="1934" height="698" alt="data_overview" src="https://github.com/user-attachments/assets/a89c5175-1b54-42d3-8e8a-72f1e1750c5d" />
