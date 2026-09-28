-- =====================================================================
-- queries_P3.sql  |  P3 지출 예측
-- DB: SQLite 3.25+ (윈도우 함수 사용)
-- 필요한 테이블: transactions (data/transactions.csv 원본 그대로)
-- 모델: SMA = 직전 3개월 단순 평균, WMA = 직전 3개월 가중 평균 (1:2:3, 최근 달이 3)
-- 블록 구분: "-- [이름]" 주석 한 줄
-- =====================================================================


-- [SETUP]
-- 1) 정제: 취소 제외 + 중복 제거 (loader.py 와 같은 규칙)
DROP VIEW IF EXISTS tx_clean;
CREATE VIEW tx_clean AS
SELECT *
FROM (
    SELECT t.*,
           substr(transaction_datetime, 1, 7)  AS ym,
           substr(transaction_datetime, 1, 10) AS tx_date,
           ROW_NUMBER() OVER (
               PARTITION BY customer_id, transaction_datetime, merchant_name, category,
                            amount, payment_method, card_product, transaction_status
               ORDER BY transaction_id
           ) AS rn
    FROM transactions t
)
WHERE rn = 1 AND transaction_status = 'APPROVED';

-- 2) 카테고리 정규화 + 대분류 (classify.py 와 같은 규칙)
DROP TABLE IF EXISTS category_map;
CREATE TABLE category_map (category_std TEXT PRIMARY KEY, big_category TEXT NOT NULL);
INSERT INTO category_map VALUES
    ('DINING','식비'), ('GROCERY','식비'), ('CONVENIENCE','식비'),
    ('CAFE','카페'), ('DELIVERY','배달'),
    ('TRANSPORT','교통'), ('FUEL','교통'),
    ('ONLINE_SHOPPING','쇼핑'), ('FASHION','쇼핑'), ('HOUSEHOLD','쇼핑'),
    ('SUBSCRIPTION','구독'), ('UTILITY','주거통신'), ('MEDICAL','의료'),
    ('EDUCATION','교육'), ('ENTERTAINMENT','여가'),
    ('TRAVEL','여행'), ('ACCOMMODATION','여행'),
    ('PET','기타'), ('BUSINESS','기타'), ('CEREMONY','기타');

DROP VIEW IF EXISTS tx_std;
CREATE VIEW tx_std AS
SELECT c.*, s.category_std, m.big_category
FROM tx_clean c
JOIN (SELECT transaction_id,
             CASE UPPER(TRIM(category))
                  WHEN 'DINNING' THEN 'DINING' WHEN 'GROCERRY' THEN 'GROCERY'
                  WHEN 'DELIVERLY' THEN 'DELIVERY' WHEN 'CAFFE' THEN 'CAFE'
                  ELSE UPPER(TRIM(category)) END AS category_std
      FROM tx_clean) s ON s.transaction_id = c.transaction_id
JOIN category_map m ON m.category_std = s.category_std;

-- 3) 고객 × 대분류 × 월 지출 (한 번이라도 쓴 고객·대분류 조합만, 안 쓴 달은 0)
DROP VIEW IF EXISTS monthly_filled;
CREATE VIEW monthly_filled AS
WITH pairs  AS (SELECT DISTINCT customer_id, big_category FROM tx_std),
     months AS (SELECT DISTINCT ym FROM tx_std),
     spend  AS (SELECT customer_id, big_category, ym, SUM(amount) AS amount
                FROM tx_std GROUP BY customer_id, big_category, ym)
SELECT p.customer_id, p.big_category, m.ym, COALESCE(s.amount, 0) AS amount
FROM pairs p CROSS JOIN months m
LEFT JOIN spend s
  ON s.customer_id = p.customer_id AND s.big_category = p.big_category AND s.ym = m.ym;


-- [P3-01 월별 전체 지출 추이]
SELECT ym, SUM(amount) AS amount, COUNT(DISTINCT customer_id) AS customers
FROM tx_std
GROUP BY ym
ORDER BY ym;


-- [P3-02 한 고객의 다음 달 대분류별 예측]
-- 파라미터: :customer_id  (예: 'C0003')
-- 2025-10 ~ 2025-12 로 2026-01 을 예측
WITH w AS (
    SELECT big_category, ym, amount,
           AVG(amount) OVER win AS sma,
           (3.0 * amount
            + 2.0 * LAG(amount, 1) OVER (PARTITION BY big_category ORDER BY ym)
            + 1.0 * LAG(amount, 2) OVER (PARTITION BY big_category ORDER BY ym)) / 6 AS wma
    FROM monthly_filled
    WHERE customer_id = :customer_id
    WINDOW win AS (PARTITION BY big_category ORDER BY ym ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)
)
SELECT big_category,
       ROUND(sma, 0) AS sma_forecast,
       ROUND(wma, 0) AS wma_forecast
FROM w
WHERE ym = '2025-12'
ORDER BY sma DESC;


-- [P3-03 백테스트: 전체 고객 MAE (4~12월)]
-- 대상 월 M 을 M-3 ~ M-1 로 예측하고 실제값과의 절대오차 평균을 비교
WITH w AS (
    SELECT customer_id, big_category, ym, amount AS actual,
           AVG(amount) OVER (PARTITION BY customer_id, big_category ORDER BY ym
                             ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS sma,
           (3.0 * LAG(amount, 1) OVER p + 2.0 * LAG(amount, 2) OVER p
            + 1.0 * LAG(amount, 3) OVER p) / 6 AS wma
    FROM monthly_filled
    WINDOW p AS (PARTITION BY customer_id, big_category ORDER BY ym)
)
SELECT COUNT(*)                          AS n,
       ROUND(AVG(ABS(actual - sma)), 0)  AS mae_sma,
       ROUND(AVG(ABS(actual - wma)), 0)  AS mae_wma
FROM w
WHERE ym >= '2025-04';


-- [P3-04 백테스트: 월별 MAE]
WITH w AS (
    SELECT customer_id, big_category, ym, amount AS actual,
           AVG(amount) OVER (PARTITION BY customer_id, big_category ORDER BY ym
                             ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS sma,
           (3.0 * LAG(amount, 1) OVER p + 2.0 * LAG(amount, 2) OVER p
            + 1.0 * LAG(amount, 3) OVER p) / 6 AS wma
    FROM monthly_filled
    WINDOW p AS (PARTITION BY customer_id, big_category ORDER BY ym)
)
SELECT ym,
       ROUND(AVG(ABS(actual - sma)), 0) AS mae_sma,
       ROUND(AVG(ABS(actual - wma)), 0) AS mae_wma
FROM w
WHERE ym >= '2025-04'
GROUP BY ym
ORDER BY ym;


-- [P3-05 이번 달 말 예상 지출 (기준일까지의 페이스)]
-- 파라미터: :customer_id, :month ('2025-12'), :as_of ('2025-12-20')
-- 고정비(SUBSCRIPTION)는 페이스에서 빼고 따로 더한다. 월 일수는 12월 기준 31일.
WITH cur AS (
    SELECT SUM(amount) AS actual_to_date,
           SUM(CASE WHEN category_std = 'SUBSCRIPTION' THEN amount ELSE 0 END) AS fixed_costs,
           CAST(MAX(substr(tx_date, 9, 2)) AS INTEGER) AS elapsed_days
    FROM tx_std
    WHERE customer_id = :customer_id AND ym = :month AND tx_date <= :as_of
)
SELECT actual_to_date, fixed_costs, elapsed_days,
       ROUND((actual_to_date - fixed_costs) * 1.0 / elapsed_days * 31 + fixed_costs, 0) AS projected_total
FROM cur;