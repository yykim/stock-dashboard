"""
분석 모듈: 초과등락률 계산, 상·하위 추출, 손절 경고 판정.
(데이터 출처와 무관 — '등락률' 컬럼을 가진 DataFrame을 입력받는다)
"""
import pandas as pd


def add_excess_return(df: pd.DataFrame, index_return: float) -> pd.DataFrame:
    """초과등락률 = 종목 등락률 − 지수 등락률 (양수=강세, 음수=약세)."""
    out = df.copy()
    out["지수등락률"] = round(index_return, 2)
    out["초과등락률"] = (out["등락률"] - index_return).round(2)
    return out


def top_bottom(df: pd.DataFrame, n: int = 10):
    """초과등락률 기준 상위 n(강세) / 하위 n(약세)."""
    ranked = df.sort_values("초과등락률", ascending=False)
    return ranked.head(n), ranked.tail(n).iloc[::-1]


def stoploss_flags(df: pd.DataFrame, threshold: float) -> pd.DataFrame:
    """초과등락률이 -threshold 이하인 종목에 '손절경고'(True) 표시."""
    out = df.copy()
    out["손절경고"] = out["초과등락률"] <= -abs(threshold)
    return out
