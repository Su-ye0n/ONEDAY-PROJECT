-- P4 유사 고객군 비교
-- src/cohort.py 의 analyze()와 동일한 3단계 완화 로직을 SQL로 재현해
-- notebooks/cohort_P4.ipynb 에서 Python 결과와 교차검증한다.
-- 입력 테이블: clean_transactions(customer_id, age_group, gender, occupation,
--              annual_income, ym, big_category, amount)
-- 파라미터: :customer_id, :month

WITH month_tx AS (
    SELECT *
    FROM clean_transactions
    WHERE ym = :month
),
profiles AS (
    SELECT DISTINCT customer_id, age_group, gender, occupation, annual_income,
        CASE
            WHEN annual_income < 40000000 THEN '4천만 미만'
            WHEN annual_income < 60000000 THEN '4천~6천'
            ELSE '6천 이상'
        END AS income_band
    FROM month_tx
),
target AS (
    SELECT * FROM profiles WHERE customer_id = :customer_id
),
stage1_peers AS (
    SELECT p.customer_id
    FROM profiles p, target t
    WHERE p.customer_id <> t.customer_id
      AND p.age_group = t.age_group
      AND p.gender = t.gender
      AND p.occupation = t.occupation
      AND p.income_band = t.income_band
),
stage2_peers AS (
    SELECT p.customer_id
    FROM profiles p, target t
    WHERE p.customer_id <> t.customer_id
      AND p.age_group = t.age_group
      AND p.gender = t.gender
      AND p.occupation = t.occupation
),
stage3_peers AS (
    SELECT p.customer_id
    FROM profiles p, target t
    WHERE p.customer_id <> t.customer_id
      AND p.age_group = t.age_group
      AND p.gender = t.gender
),
stage_counts AS (
    SELECT
        (SELECT COUNT(*) FROM stage1_peers) AS n1,
        (SELECT COUNT(*) FROM stage2_peers) AS n2,
        (SELECT COUNT(*) FROM stage3_peers) AS n3
),
chosen AS (
    SELECT
        CASE
            WHEN n1 >= 20 THEN 1
            WHEN n2 >= 20 THEN 2
            ELSE 3
        END AS cohort_stage
    FROM stage_counts
),
peers AS (
    SELECT customer_id FROM stage1_peers WHERE (SELECT cohort_stage FROM chosen) = 1
    UNION ALL
    SELECT customer_id FROM stage2_peers WHERE (SELECT cohort_stage FROM chosen) = 2
    UNION ALL
    SELECT customer_id FROM stage3_peers WHERE (SELECT cohort_stage FROM chosen) = 3
),
categories AS (
    SELECT DISTINCT big_category FROM month_tx
),
grid AS (
    SELECT peers.customer_id, categories.big_category
    FROM peers CROSS JOIN categories
),
peer_spend AS (
    SELECT grid.customer_id, grid.big_category,
           COALESCE(SUM(month_tx.amount), 0) AS spend
    FROM grid
    LEFT JOIN month_tx
        ON month_tx.customer_id = grid.customer_id
       AND month_tx.big_category = grid.big_category
    GROUP BY grid.customer_id, grid.big_category
),
peer_ranked AS (
    SELECT big_category, spend,
           ROW_NUMBER() OVER (PARTITION BY big_category ORDER BY spend) AS rn,
           COUNT(*) OVER (PARTITION BY big_category) AS cnt
    FROM peer_spend
),
peer_stats AS (
    SELECT ps.big_category,
           AVG(ps.spend) AS peer_mean,
           (SELECT AVG(spend) FROM peer_ranked r
             WHERE r.big_category = ps.big_category
               AND r.rn IN ((r.cnt + 1) / 2, (r.cnt + 2) / 2)) AS peer_median
    FROM peer_spend ps
    GROUP BY ps.big_category
),
my_spend AS (
    SELECT categories.big_category,
           COALESCE(SUM(month_tx.amount), 0) AS my_spend
    FROM categories
    LEFT JOIN month_tx
        ON month_tx.customer_id = :customer_id
       AND month_tx.big_category = categories.big_category
    GROUP BY categories.big_category
)
SELECT
    (SELECT cohort_stage FROM chosen) AS cohort_stage,
    (SELECT COUNT(*) FROM peers) AS peer_count,
    my_spend.big_category AS big_category,
    my_spend.my_spend AS my_spend,
    peer_stats.peer_mean AS peer_mean,
    peer_stats.peer_median AS peer_median,
    my_spend.my_spend - peer_stats.peer_median AS diff_from_median
FROM my_spend
JOIN peer_stats ON peer_stats.big_category = my_spend.big_category
WHERE (SELECT COUNT(*) FROM peers) > 0
ORDER BY ABS(my_spend.my_spend - peer_stats.peer_median) DESC
LIMIT 1;