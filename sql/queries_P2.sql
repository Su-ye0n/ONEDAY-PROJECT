-- =====================================================================
-- queries_P2.sql  |  P2 카테고리 정제 + 소비 변화 분석
-- DB: SQLite 3.25+ (윈도우 함수 사용)
-- 전제: transactions_clean 테이블 = 중복·취소 제거된 거래 + ym(YYYY-MM) 컬럼
--       (notebooks/change_P2.ipynb 에서 생성)
-- 블록 구분: "-- [이름]" 주석 한 줄. 노트북이 이 표시로 쿼리를 잘라 실행한다.
-- =====================================================================


-- [SETUP]
-- 표준 카테고리 → 대분류 매핑 테이블 (src/classify.py 의 BIG_CATEGORY 와 동일해야 함)
DROP TABLE IF EXISTS category_map;
CREATE TABLE category_map (
    category_std TEXT PRIMARY KEY,
    big_category TEXT NOT NULL
);
INSERT INTO category_map VALUES
    ('DINING','식비'), ('GROCERY','식비'), ('CONVENIENCE','식비'),
    ('CAFE','카페'), ('DELIVERY','배달'),
    ('TRANSPORT','교통'), ('FUEL','교통'),
    ('ONLINE_SHOPPING','쇼핑'), ('FASHION','쇼핑'), ('HOUSEHOLD','쇼핑'),
    ('SUBSCRIPTION','구독'), ('UTILITY','주거통신'), ('MEDICAL','의료'),
    ('EDUCATION','교육'), ('ENTERTAINMENT','여가'),
    ('TRAVEL','여행'), ('ACCOMMODATION','여행'),
    ('PET','기타'), ('BUSINESS','기타'), ('CEREMONY','기타');

-- 정규화 뷰: 공백 제거 → 대문자 → 오타 교정 → 대분류 JOIN
DROP VIEW IF EXISTS tx_std;
CREATE VIEW tx_std AS
SELECT t.*,
       s.category_std,
       m.big_category
FROM transactions_clean t
JOIN (
    SELECT transaction_id,
           CASE UPPER(TRIM(category))
                WHEN 'DINNING'   THEN 'DINING'
                WHEN 'GROCERRY'  THEN 'GROCERY'
                WHEN 'DELIVERLY' THEN 'DELIVERY'
                WHEN 'CAFFE'     THEN 'CAFE'
                ELSE UPPER(TRIM(category))
           END AS category_std
    FROM transactions_clean
) s ON s.transaction_id = t.transaction_id
LEFT JOIN category_map m ON m.category_std = s.category_std;


-- [P2-01 원본 카테고리 표기 변형 목록]
-- 같은 카테고리가 몇 가지 표기로 들어와 있는지 확인
SELECT UPPER(TRIM(category)) AS category_upper,
       category              AS category_raw,
       COUNT(*)              AS rows,
       SUM(amount)           AS amount
FROM transactions_clean
GROUP BY UPPER(TRIM(category)), category
ORDER BY category_upper, rows DESC;


-- [P2-02 정규화 결과 검증]
-- 기대값: n_category_raw = 64, n_category_std = 20, unmapped = 0
SELECT COUNT(DISTINCT category)                                   AS n_category_raw,
       COUNT(DISTINCT category_std)                               AS n_category_std,
       SUM(CASE WHEN big_category IS NULL THEN 1 ELSE 0 END)      AS unmapped,
       SUM(amount)                                                AS total_amount
FROM tx_std;


-- [P2-03 가맹점별 카테고리 일관성]
-- 정규화 후 한 가맹점이 2개 이상 카테고리에 걸리면 사전 충돌. 기대값: 0행
SELECT merchant_name,
       COUNT(DISTINCT category_std) AS n_category,
       GROUP_CONCAT(DISTINCT category_std) AS categories
FROM tx_std
WHERE merchant_name IS NOT NULL
GROUP BY merchant_name
HAVING COUNT(DISTINCT category_std) > 1;


-- [P2-04 가맹점명 결측 현황]
SELECT big_category,
       COUNT(*)    AS missing_merchant_rows,
       SUM(amount) AS amount
FROM tx_std
WHERE merchant_name IS NULL
GROUP BY big_category
ORDER BY missing_merchant_rows DESC;


-- [P2-05 대분류별 월 지출 (전체 고객)]
SELECT ym,
       big_category,
       SUM(amount)                 AS amount,
       COUNT(*)                    AS tx_count,
       COUNT(DISTINCT customer_id) AS customers
FROM tx_std
GROUP BY ym, big_category
ORDER BY ym, amount DESC;


-- [P2-06 고객별 월 변화표 (전체)]
-- 지출이 없는 달을 0으로 채운 뒤(grid) LAG / 직전 3개월 평균 계산.
-- 0을 채우지 않으면 LAG가 '실제 전월'이 아니라 '마지막으로 쓴 달'을 가리킨다.
WITH customers AS (SELECT DISTINCT customer_id FROM tx_std),
     months    AS (SELECT DISTINCT ym FROM tx_std),
     cats      AS (SELECT DISTINCT big_category FROM category_map),
     grid AS (
        SELECT c.customer_id, m.ym, k.big_category
        FROM customers c CROSS JOIN months m CROSS JOIN cats k
     ),
     spend AS (
        SELECT customer_id, ym, big_category, SUM(amount) AS amount
        FROM tx_std
        GROUP BY customer_id, ym, big_category
     ),
     filled AS (
        SELECT g.customer_id, g.ym, g.big_category,
               COALESCE(s.amount, 0) AS amount
        FROM grid g
        LEFT JOIN spend s
          ON s.customer_id = g.customer_id AND s.ym = g.ym
         AND s.big_category = g.big_category
     )
SELECT customer_id, ym, big_category, amount,
       LAG(amount) OVER w AS prev_amount,
       AVG(amount) OVER (PARTITION BY customer_id, big_category ORDER BY ym
                         ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS avg_3m
FROM filled
WINDOW w AS (PARTITION BY customer_id, big_category ORDER BY ym)
ORDER BY customer_id, big_category, ym;


-- [P2-07 한 고객·한 달의 급증/급감 판정]
-- 파라미터: :customer_id, :month  (예: 'C0003', '2025-12')
-- 판정 기준은 src/change.py 와 동일: ±30% 이상 AND ±3만 원 이상
WITH spend AS (
        SELECT ym, big_category, SUM(amount) AS amount
        FROM tx_std
        WHERE customer_id = :customer_id
        GROUP BY ym, big_category
     ),
     grid AS (
        SELECT m.ym, k.big_category
        FROM (SELECT DISTINCT ym FROM tx_std) m
        CROSS JOIN (SELECT DISTINCT big_category FROM category_map) k
     ),
     filled AS (
        SELECT g.ym, g.big_category, COALESCE(s.amount, 0) AS amount
        FROM grid g
        LEFT JOIN spend s ON s.ym = g.ym AND s.big_category = g.big_category
     ),
     w AS (
        SELECT ym, big_category, amount,
               AVG(amount) OVER (PARTITION BY big_category ORDER BY ym
                                 ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS avg_3m
        FROM filled
     )
SELECT big_category,
       amount,
       ROUND(avg_3m, 0)            AS avg_3m,
       ROUND(amount - avg_3m, 0)   AS diff_3m,
       ROUND(100.0 * (amount - avg_3m) / NULLIF(avg_3m, 0), 1) AS pct_3m,
       CASE
           WHEN avg_3m = 0 AND amount >= 30000 THEN '신규'
           WHEN (amount - avg_3m) >=  30000 AND amount >= avg_3m * 1.3 THEN '급증'
           WHEN (amount - avg_3m) <= -30000 AND amount <= avg_3m * 0.7 THEN '급감'
           ELSE '유지'
       END AS status
FROM w
WHERE ym = :month
ORDER BY ABS(amount - avg_3m) DESC;


-- [P2-08 월별 급증 판정 비율]
-- 기준(±30%, ±3만 원)이 너무 느슨한지 확인하는 용도
WITH customers AS (SELECT DISTINCT customer_id FROM tx_std),
     months    AS (SELECT DISTINCT ym FROM tx_std),
     cats      AS (SELECT DISTINCT big_category FROM category_map),
     spend AS (
        SELECT customer_id, ym, big_category, SUM(amount) AS amount
        FROM tx_std
        GROUP BY customer_id, ym, big_category
     ),
     filled AS (
        SELECT c.customer_id, m.ym, k.big_category, COALESCE(s.amount, 0) AS amount
        FROM customers c CROSS JOIN months m CROSS JOIN cats k
        LEFT JOIN spend s
          ON s.customer_id = c.customer_id AND s.ym = m.ym
         AND s.big_category = k.big_category
     ),
     w AS (
        SELECT customer_id, ym, big_category, amount,
               AVG(amount) OVER (PARTITION BY customer_id, big_category ORDER BY ym
                                 ROWS BETWEEN 3 PRECEDING AND 1 PRECEDING) AS avg_3m
        FROM filled
     ),
     flag AS (
        SELECT ym,
               CASE WHEN avg_3m > 0 AND amount - avg_3m >= 30000
                     AND amount >= avg_3m * 1.3 THEN 1 ELSE 0 END AS is_spike
        FROM w
        WHERE ym > (SELECT MIN(ym) FROM tx_std)
     )
SELECT ym,
       SUM(is_spike)                          AS spike_cells,
       COUNT(*)                               AS cells,
       ROUND(100.0 * SUM(is_spike) / COUNT(*), 1) AS spike_pct
FROM flag
GROUP BY ym
ORDER BY ym;