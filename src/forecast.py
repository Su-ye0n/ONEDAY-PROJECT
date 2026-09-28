import pandas as pd
import numpy as np

def predict_next_month_categories(df_user: pd.DataFrame, target_month: str = '2025-12') -> dict:
    """
    2. 다음 달 카테고리(대분류)별 지출 예측 함수
    
    - 기본 모델: 최근 3개월 단순 이동평균 (SMA)
    - 개선 모델: 최근 3개월 가중 이동평균 (WMA, 최근 월일수록 가중치 높음 1:2:3)
    """
    # 1. target_month 이전 3개월의 YM 목록 구하기 (예: '2025-12' 기준 -> '2025-09', '2025-10', '2025-11')
    target_dt = pd.to_datetime(f"{target_month}-01")
    past_3m_yms = [(target_dt - pd.DateOffset(months=i)).strftime('%Y-%m') for i in range(3, 0, -1)]
    
    # 2. 최근 3개월간의 APPROVED 거래 데이터만 필터링
    df_3m = df_user[
        (df_user['ym'].isin(past_3m_yms)) & 
        (df_user['transaction_status'] == 'APPROVED')
    ]
    
    if df_3m.empty:
        return {
            "sma_forecast": {},
            "wma_forecast": {},
            "top_category": None,
            "top_category_amount": 0
        }
    
    # 3. 월별 x 대분류(big_category) 지출액 피벗 테이블 생성
    # (P2 정제 전이라 big_category가 없는 경우 category_std 사용)
    cat_col = 'big_category' if 'big_category' in df_3m.columns else 'category_std'
    
    pivot_df = df_3m.pivot_table(
        index='ym', 
        columns=cat_col, 
        values='amount', 
        aggfunc='sum'
    ).reindex(past_3m_yms).fillna(0)  # 거래 없는 달은 0으로 채움
    
    # 4. 기본 모델: 3개월 단순 이동평균 (SMA)
    sma_series = pivot_df.mean(axis=0)
    sma_forecast = sma_series.astype(int).to_dict()
    
    # 5. 개선 모델: 3개월 가중 이동평균 (WMA, 가중치 [1/6, 2/6, 3/6])
    weights = np.array([1/6, 2/6, 3/6])
    wma_series = pivot_df.apply(lambda col: np.dot(col.values, weights), axis=0)
    wma_forecast = wma_series.astype(int).to_dict()
    
    # 6. 다음 달 지출 예측 1위 카테고리 추출 (WMA 모델 기준)
    if not wma_series.empty:
        top_cat = wma_series.idxmax()
        top_amount = int(wma_series.max())
    else:
        top_cat, top_amount = "기타", 0
        
    return {
        "past_3m_used": past_3m_yms,
        "sma_forecast": sma_forecast,
        "wma_forecast": wma_forecast,
        "top_category": top_cat,
        "top_category_amount": top_amount
    }


# ==========================================
# 1번과 2번을 모두 통합한 analyze 함수 (report.py 연결용)
# ==========================================
def analyze(df: pd.DataFrame, customer_id: str, month: str) -> dict:
    """
    공통 규약 analyze 함수 (1번 + 2번 결과 종합)
    """
    # 해당 고객 데이터만 추출
    df_user = df[df['customer_id'] == customer_id]
    
    # P5 고정비 연동 전 임시 계산 (SUBSCRIPTION 카테고리)
    fixed_costs = 0
    df_curr_sub = df_user[(df_user['ym'] == month) & (df_user['category_std'] == 'SUBSCRIPTION')]
    if not df_curr_sub.empty:
        fixed_costs = int(df_curr_sub['amount'].sum())
        
    # 1. 이번 달 말 예상 계산
    from forecast import calculate_current_month_forecast  # 동일 파일 내 호출
    res_forecast = calculate_current_month_forecast(df_user, current_month=month, fixed_costs=fixed_costs)
    
    # 2. 다음 달 카테고리별 지출 예측 계산
    res_next_cat = predict_next_month_categories(df_user, target_month=month)
    
    return {
        "feature": "forecast",
        "title": "지출 예측",
        "message": res_forecast["message"],
        "data": {
            "projected_total": res_forecast["projected_total"],
            "diff_from_last_month": res_forecast["diff_from_last_month"],
            "next_month_top_category": res_next_cat["top_category"],
            "next_month_top_amount": res_next_cat["top_category_amount"],
            "sma_forecast_by_cat": res_next_cat["sma_forecast"],
            "wma_forecast_by_cat": res_next_cat["wma_forecast"]
        }
    }


# ==========================================
# 테스트 실행부
# ==========================================
if __name__ == "__main__":
    # 테스트 데이터 생성
    sample_data = {
        'customer_id': ['C001']*6,
        'transaction_status': ['APPROVED']*6,
        'ym': ['2025-09', '2025-10', '2025-11', '2025-09', '2025-10', '2025-11'],
        'dt': [pd.Timestamp('2025-09-10'), pd.Timestamp('2025-10-10'), pd.Timestamp('2025-11-10'),
               pd.Timestamp('2025-09-15'), pd.Timestamp('2025-10-15'), pd.Timestamp('2025-11-15')],
        'category_std': ['식비', '식비', '식비', '쇼핑', '쇼핑', '쇼핑'],
        'big_category': ['식비', '식비', '식비', '쇼핑', '쇼핑', '쇼핑'],
        'amount': [300000, 400000, 500000, 100000, 200000, 150000]
    }
    df_test = pd.DataFrame(sample_data)
    
    # 2025년 12월 기준 다음 달 예측 실행
    next_cat_res = predict_next_month_categories(df_test, target_month='2025-12')
    print("--- 2번 다음 달 예측 결과 ---")
    print("단순이동평균(SMA) 예측:", next_cat_res["sma_forecast"])
    print("가중이동평균(WMA) 예측:", next_cat_res["wma_forecast"])
    print(f"가장 지출이 클 것으로 예상되는 카테고리: {next_cat_res['top_category']} ({next_cat_res['top_category_amount']:,}원)")

    def run_backtest(df_user: pd.DataFrame, test_month: str = '2025-12') -> dict:
    # 1~11월 데이터로 12월을 예측하고 실제 12월 데이터와 비교하여 MAE 계산 
    # 1. 실제 12월 데이터 추출 (실제값)
        cat_col = 'big_category' if 'big_category' in df_user.columns else 'category_std'
        
        df_actual = df_user[
            (df_user['ym'] == test_month) & 
            (df_user['transaction_status'] == 'APPROVED')
        ]
        actual_series = df_actual.groupby(cat_col)['amount'].sum()
        
        # 2. 12월 이전(1~11월) 데이터만 사용하여 12월 예측 실행
        df_train = df_user[df_user['ym'] < test_month]
        pred_res = predict_next_month_categories(df_train, target_month=test_month)
        
        sma_pred = pred_res.get("sma_series", pd.Series(dtype=float))
        wma_pred = pred_res.get("wma_series", pd.Series(dtype=float))
        
        if actual_series.empty or sma_pred.empty:
            return {
                "mae_sma": 0,
                "mae_wma": 0,
                "selected_model": "SMA (데이터 부족)",
                "improvement": "N/A"
            }
        
        # 3. 실제값과 예측값의 카테고리 인덱스 맞추기
        all_cats = actual_series.index.union(sma_pred.index)
        y_true = actual_series.reindex(all_cats, fill_value=0)
        y_sma = sma_pred.reindex(all_cats, fill_value=0)
        y_wma = wma_pred.reindex(all_cats, fill_value=0)
        
        # 4. MAE (Mean Absolute Error) 계산
        mae_sma = float(np.mean(np.abs(y_true - y_sma)))
        mae_wma = float(np.mean(np.abs(y_true - y_wma)))
        
        # 5. 오차가 더 작은 우수 모델 선정
        if mae_wma < mae_sma:
            selected_model = "WMA (가중 이동평균)"
            imp_pct = round(((mae_sma - mae_wma) / mae_sma) * 100, 1)
            improvement = f"SMA 대비 오차 {imp_pct}% 감소"
        else:
            selected_model = "SMA (단순 이동평균)"
            improvement = "기본 모델 채택"
            
        return {
            "mae_sma": round(mae_sma, 0),
            "mae_wma": round(mae_wma, 0),
            "selected_model": selected_model,
            "improvement": improvement
        }


# ==========================================
# 팀 프로젝트 공통 규약 인터페이스 (report.py 연결용)
# ==========================================
def analyze(df: pd.DataFrame, customer_id: str, month: str) -> dict:
    df_user = df[df['customer_id'] == customer_id]
    
    # P5 고정비 연동 전 임시 계산 (SUBSCRIPTION 카테고리)
    fixed_costs = 0
    df_curr_sub = df_user[(df_user['ym'] == month) & (df_user['category_std'] == 'SUBSCRIPTION')]
    if not df_curr_sub.empty:
        fixed_costs = int(df_curr_sub['amount'].sum())
        
    # 1. 이번 달 말 예상 계산
    res_forecast = calculate_current_month_forecast(df_user, current_month=month, fixed_costs=fixed_costs)
    
    # 2. 다음 달 카테고리별 지출 예측 계산
    res_next_cat = predict_next_month_categories(df_user, target_month=month)
    
    # 3. 백테스트 계산
    res_backtest = run_backtest(df_user, test_month=month)
    
    return {
        "feature": "forecast",
        "title": "지출 예측",
        "message": res_forecast["message"],
        "data": {
            "projected_total": res_forecast["projected_total"],
            "diff_from_last_month": res_forecast["diff_from_last_month"],
            "next_month_top_category": res_next_cat["top_category"],
            "next_month_top_amount": res_next_cat["top_category_amount"],
            "sma_forecast_by_cat": res_next_cat["sma_forecast"],
            "wma_forecast_by_cat": res_next_cat["wma_forecast"],
            "backtest": res_backtest
        }
    }
