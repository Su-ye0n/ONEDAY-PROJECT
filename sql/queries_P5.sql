-- P5 정기결제 탐지 SQL 교차검증
-- 조건:
-- 1. 승인 거래
-- 2. 가맹점명이 존재
-- 3. 동일 고객 + 동일 가맹점에서 3개월 이상 반복
-- 4. 결제금액 동일
-- 5. 결제일 범위 6일 이내 (기준일 ±3일)

SELECT
    customer_id,
    merchant_name,
    COUNT(DISTINCT SUBSTR(transaction_datetime, 1, 7)) AS active_months,
    COUNT(*) AS payment_count,
    AVG(amount) AS avg_amount,
    MIN(amount) AS min_amount,
    MAX(amount) AS max_amount,
    MIN(CAST(SUBSTR(transaction_datetime, 9, 2) AS INTEGER)) AS min_day,
    MAX(CAST(SUBSTR(transaction_datetime, 9, 2) AS INTEGER)) AS max_day
FROM transactions
WHERE transaction_status = 'APPROVED'
  AND merchant_name IS NOT NULL
GROUP BY customer_id, merchant_name
HAVING COUNT(DISTINCT SUBSTR(transaction_datetime, 1, 7)) >= 3
   AND MIN(amount) = MAX(amount)
   AND (
       MAX(CAST(SUBSTR(transaction_datetime, 9, 2) AS INTEGER))
       - MIN(CAST(SUBSTR(transaction_datetime, 9, 2) AS INTEGER))
   ) <= 6
ORDER BY customer_id, merchant_name;