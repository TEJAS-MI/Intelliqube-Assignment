# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum_excel_style(series, n):
    result = pd.Series([np.nan] * len(series), index=series.index)
    if len(series) <= n:
        return result
    arr = series.values
    initial_sum = np.nansum(arr[1:n+1])
    result.iloc[n] = initial_sum
    for i in range(n+1, len(arr)):
        prev = result.iloc[i-1]
        if np.isnan(prev):
            result.iloc[i] = np.nan
        else:
            result.iloc[i] = prev - (prev / n) + arr[i]
    return result


def detect_ohlc_columns(df):
    lower = {c.lower(): c for c in df.columns}
    mapping = {}
    candidates = {'open': ['open', 'o'], 'high': ['high', 'h'], 'low': ['low', 'l'], 'close': ['close', 'c']}
    for key, opts in candidates.items():
        found = None
        for opt in opts:
            if opt in lower:
                found = lower[opt]
                break
        if not found:
            for name_lower, orig in lower.items():
                if key in name_lower:
                    found = orig
                    break
        mapping[key] = found
    return mapping


def calculate_adx(input_df):
    df = input_df.copy()
    ohlc_map = detect_ohlc_columns(df)
    if None in ohlc_map.values():
        missing = [k for k, v in ohlc_map.items() if v is None]
        raise ValueError("Missing OHLC columns in input CSV: " + ", ".join(missing))

    first_col = df.columns[0]
    date_col = first_col if first_col not in ohlc_map.values() else None

    df = df.rename(columns={
        ohlc_map['open']: 'Open',
        ohlc_map['high']: 'High',
        ohlc_map['low']: 'Low',
        ohlc_map['close']: 'Close'
    })

    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(
        pd.to_numeric, errors='coerce'
    )

    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

    if len(df) >= 1:
        df.loc[df.index[0], 'TR'] = np.nan

    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], np.nan)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], np.nan)

    # >>> FIX: zero from 3rd row onward ONLY <<<
    if len(df) > 2:
    df.loc[df.index[2]:, '+DM 1'] = df.loc[df.index[2]:, '+DM 1'].fillna(0)
     df.loc[df.index[2]:, '-DM 1'] = df.loc[df.index[2]:, '-DM 1'].fillna(0)
    # >>> END FIX <<<

    N = 14
    df['TR14'] = wilder_sum_excel_style(df['TR'], N)
    df['+DM14'] = wilder_sum_excel_style(df['+DM 1'].fillna(0), N)
    df['-DM14'] = wilder_sum_excel_style(df['-DM 1'].fillna(0), N)

    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    adx = pd.Series([np.nan] * len(df), index=df.index)
    start = N
    end = 2 * N - 1
    if len(df) > end:
        initial_adx = df['DX'].iloc[start:end + 1].mean()
        adx.iloc[end] = initial_adx
        for i in range(end + 1, len(df)):
            prev = adx.iloc[i - 1]
            adx.iloc[i] = ((prev * (N - 1)) + df['DX'].iloc[i]) / N

    df['ADX'] = adx

    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].round(4)

    final = []
    if date_col is not None:
        final.append(date_col)
        df[date_col] = df[date_col].astype(str)

    final += [
        'Open', 'High', 'Low', 'Close',
        'TR', '+DM 1', '-DM 1',
        'TR14', '+DM14', '-DM14',
        '+DI14', '-DI14',
        'DI 14 Diff', 'DI 14 Sum',
        'DX', 'ADX'
    ]

    present = [c for c in final if c in df.columns]
    return df[present]
