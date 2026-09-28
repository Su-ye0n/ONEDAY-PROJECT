-- P6 할부 분석 SQL
-- 기준월: 2025-09
-- 거래 발생 월을 1회차 납부월로 가정

WITH params AS (
    SELECT '2025-09' AS target_month
),

installment_base AS (
    SELECT
        t.transaction_id,
        t.customer_id,
        t.transaction_datetime,
        t.merchant_name,
        t.amount,
        t.installment_months,

        -- 월 납입액
        t.amount * 1.0 / t.installment_months AS monthly_payment,

        -- 거래 발생 월부터 기준월까지 경과 회차
        (
            (
                CAST(SUBSTR(p.target_month, 1, 4) AS INTEGER)
                - CAST(SUBSTR(t.transaction_datetime, 1, 4) AS INTEGER)
            ) * 12
            +
            (
                CAST(SUBSTR(p.target_month, 6, 2) AS INTEGER)
                - CAST(SUBSTR(t.transaction_datetime, 6, 2) AS INTEGER)
            )
            + 1
        ) AS elapsed_months

    FROM transactions t
    CROSS JOIN params p

    WHERE t.transaction_status = 'APPROVED'
      AND t.installment_months > 0

      -- 기준월 이후의 미래 거래 제외
      AND SUBSTR(t.transaction_datetime, 1, 7) <= p.target_month
),

installment_status AS (
    SELECT
        *,

        -- 납부 완료 회차 보정
        CASE
            WHEN elapsed_months < 0 THEN 0
            WHEN elapsed_months > installment_months
                THEN installment_months
            ELSE elapsed_months
        END AS paid_months

    FROM installment_base
)

SELECT
    transaction_id,
    customer_id,
    transaction_datetime,
    merchant_name,
    amount,
    installment_months,
    monthly_payment,
    paid_months,

    -- 남은 회차
    installment_months - paid_months
        AS remaining_months,

    -- 남은 할부금
    monthly_payment
        * (installment_months - paid_months)
        AS remaining_amount,

    -- 다음 달 납입 예정액
    CASE
        WHEN installment_months - paid_months > 0
            THEN monthly_payment
        ELSE 0
    END AS next_month_payment

FROM installment_status

ORDER BY customer_id, transaction_datetime;