# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum_excel_style(series, n):
    result = pd.Series([np.nan] * len(series), index=series.index)
    if len(series) <= n:
        return result

    arr = series.values
    initial_sum = np.nansum(arr[1:n+1])  # Excel: skip first row
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

    # Identify OHLC columns
    ohlc_map = detect_ohlc_columns(df)
    if None in ohlc_map.values():
        missing = [k for k, v in ohlc_map.items() if v is None]
        raise ValueError("Missing OHLC columns: " + ", ".join(missing))

    # Detect date column (first column if not OHLC)
    first_col = df.columns[0]
    date_col = first_col if first_col not in ohlc_map.values() else None

    # Rename OHLC to standard names
    df = df.rename(columns={
        ohlc_map['open']: 'Open',
        ohlc_map['high']: 'High',
        ohlc_map['low']: 'Low',
        ohlc_map['close']: 'Close'
    })

    # Convert numeric
    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(
        pd.to_numeric, errors='coerce'
    )

    # Previous values
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    # TR calculation
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

    # Excel keeps first row blank
    df.loc[df.index[0], 'TR'] = np.nan

    # DM values
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], np.nan)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], np.nan)

    # -----------------------------------------------------------------------
    # 🔥 EXACT EXCEL BEHAVIOUR:
    # Row1 = blank, Row2 = blank, Row3+ = show 0.00 instead of blank.
    # -----------------------------------------------------------------------
    # Force row 3 (index 1) to show 0 instead of blank
if len(df) > 1:
    df.loc[df.index[1], '+DM 1'] = df.loc[df.index[1], '+DM 1'] if not np.isnan(df.loc[df.index[1], '+DM 1']) else 0
    df.loc[df.index[1], '-DM 1'] = df.loc[df.index[1], '-DM 1'] if not np.isnan(df.loc[df.index[1], '-DM 1']) else 0


    # Wilder sums
    N = 14
    df['TR14'] = wilder_sum_excel_style(df['TR'], N)
    df['+DM14'] = wilder_sum_excel_style(df['+DM 1'], N)
    df['-DM14'] = wilder_sum_excel_style(df['-DM 1'], N)

    # DI values
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    # ADX
    adx = pd.Series([np.nan] * len(df), index=df.index)

    start = N
    end = 2 * N - 1

    if len(df) > end:
        adx.iloc[end] = df['DX'].iloc[start:end + 1].mean()
        for i in range(end + 1, len(df)):
            prev = adx.iloc[i - 1]
            adx.iloc[i] = ((prev * (N - 1)) + df['DX'].iloc[i]) / N

    df['ADX'] = adx

    # -----------------------------------------------------------------------
    # 🔥 FORCE EXACTLY TWO DECIMALS FOR ALL NUMERIC COLUMNS
    # -----------------------------------------------------------------------
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].applymap(lambda x: np.nan if pd.isna(x) else float(f"{x:.2f}"))

    # Build output column order
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
