-- [SETUP]
DROP VIEW IF EXISTS tx_clean;
CREATE VIEW tx_clean AS
SELECT *
FROM (
    SELECT t.*,
           substr(transaction_datetime, 1, 7)  AS ym,
           substr(transaction_datetime, 1, 10) AS tx_date,
           ROW_NUMBER() OVER (
               PARTITION BY customer_id, transaction_datetime, merchant_name, category,
                            amount, payment_method, card_product, transaction_status
               ORDER BY transaction_id
           ) AS rn
    FROM transactions t
)
WHERE rn = 1
  AND transaction_status = 'APPROVED';

-- 카드 결제만 (계좌이체는 카드 실적이 아님)
DROP VIEW IF EXISTS card_tx;
CREATE VIEW card_tx AS
SELECT *
FROM tx_clean
WHERE payment_method <> 'BANK_TRANSFER'
  AND card_product IS NOT NULL;



-- [P7-01 정제 전후 건수]
SELECT (SELECT COUNT(*) FROM transactions)                                   AS raw_rows,
       (SELECT COUNT(*) FROM transactions WHERE transaction_status = 'CANCELLED') AS cancelled,
       (SELECT COUNT(*) FROM tx_clean)                                       AS clean_rows,
       (SELECT COUNT(*) FROM card_tx)                                        AS card_rows;



-- [P7-02 이번 달 고객 x 카드 실적 (기준일 12/20)]
-- 결제가 없는 카드도 0원으로 나오도록 고객 x 카드 전체 조합에 LEFT JOIN
WITH pairs AS (
    SELECT DISTINCT customer_id, card_product FROM card_tx
),
perf AS (
    SELECT customer_id, card_product,
           SUM(amount) AS perf_amount,
           COUNT(*)    AS tx_cnt
    FROM card_tx
    WHERE tx_date BETWEEN '2025-12-01' AND '2025-12-20'
    GROUP BY customer_id, card_product
)
SELECT p.customer_id, p.card_product,
       COALESCE(f.perf_amount, 0) AS perf_amount,
       COALESCE(f.tx_cnt, 0)      AS tx_cnt
FROM pairs p
LEFT JOIN perf f
  ON f.customer_id = p.customer_id AND f.card_product = p.card_product
ORDER BY p.customer_id, p.card_product;



-- [P7-03 전월(11월) 고객 x 카드 실적]
-- 이번 달 혜택 구간은 보통 전월 실적으로 정해지므로 함께 확인
SELECT customer_id, card_product,
       SUM(amount) AS prev_perf_amount,
       COUNT(*)    AS prev_tx_cnt
FROM card_tx
WHERE ym = '2025-11'
GROUP BY customer_id, card_product
ORDER BY customer_id, card_product;



-- [P7-04 SQL 실적 vs Pandas 결과 교차검증]
-- 기대값: mismatch_amount = 0, mismatch_cnt = 0
WITH perf AS (
    SELECT customer_id, card_product,
           SUM(amount) AS perf_amount,
           COUNT(*)    AS tx_cnt
    FROM card_tx
    WHERE tx_date BETWEEN '2025-12-01' AND '2025-12-20'
    GROUP BY customer_id, card_product
)
SELECT COUNT(*) AS compared_rows,
       SUM(CASE WHEN r.perf_amount <> COALESCE(f.perf_amount, 0) THEN 1 ELSE 0 END) AS mismatch_amount,
       SUM(CASE WHEN r.tx_cnt      <> COALESCE(f.tx_cnt, 0)      THEN 1 ELSE 0 END) AS mismatch_cnt
FROM p7_result r
LEFT JOIN perf f
  ON f.customer_id = r.customer_id AND f.card_product = r.card_product;



-- [P7-05 부족액 계산 검증]
-- shortfall = 다음 구간 기준액 - 현재 실적 (0 미만이면 0). 기대값: mismatch = 0
SELECT COUNT(*) AS rows_with_threshold,
       SUM(CASE WHEN shortfall <> MAX(next_threshold - perf_amount, 0) THEN 1 ELSE 0 END) AS mismatch
FROM p7_result
WHERE next_threshold IS NOT NULL;



-- [P7-06 카드별 실적 달성 현황]
SELECT card_product,
       card_name,
       COUNT(*)                                                   AS customers,
       ROUND(AVG(perf_amount), 0)                                 AS avg_perf,
       SUM(CASE WHEN achieved_tier >= 1 THEN 1 ELSE 0 END)        AS achieved,
       ROUND(100.0 * SUM(CASE WHEN achieved_tier >= 1 THEN 1 ELSE 0 END) / COUNT(*), 1) AS achieved_pct,
       SUM(benefit_this_month)                                    AS total_benefit
FROM p7_result
GROUP BY card_product, card_name
ORDER BY card_product;



-- [P7-07 조금만 더 쓰면 되는 고객 (부족액 5만 원 이하)]
-- 알림 효과가 가장 큰 대상: 적은 추가 결제로 혜택을 되찾을 수 있음
SELECT customer_id, card_product, perf_amount, next_threshold, shortfall,
       missed_if_short, recommend_category, message
FROM p7_result
WHERE shortfall > 0
  AND shortfall <= 50000
  AND missed_if_short > 0
ORDER BY missed_if_short DESC, shortfall ASC;



-- [P7-08 한 고객의 카드별 현황]
-- 파라미터: :customer_id  (예: 'C0001')
SELECT card_product, card_name, perf_amount, tx_cnt, achieved_tier,
       next_threshold, shortfall, benefit_this_month, missed_if_short, message
FROM p7_result
WHERE customer_id = :customer_id
ORDER BY CASE WHEN shortfall > 0 AND missed_if_short > 0
              THEN 1.0 * missed_if_short / shortfall ELSE 0 END DESC;