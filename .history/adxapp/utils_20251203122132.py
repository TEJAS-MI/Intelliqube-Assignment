# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum_excel_style(series, n):
    """
    Excel-style Wilder Smoothing:
    • First valid smoothing appears at index n
    • Uses SUM(series[1:n+1]) for Excel-matching behavior
    """
    result = pd.Series([np.nan] * len(series), index=series.index)

    if len(series) <= n:
        return result

    arr = series.values

    # Excel initial sum = sum of values from row 2 to row n+1
    initial_sum = np.nansum(arr[1:n+1])
    result.iloc[n] = initial_sum

    # Wilder smoothing forward
    for i in range(n + 1, len(arr)):
        prev = result.iloc[i - 1]

        if np.isnan(prev):
            result.iloc[i] = np.nan
        else:
            result.iloc[i] = prev - (prev / n) + arr[i]

    return result


def detect_ohlc_columns(df):
    """Automatically detect OHLC column names."""
    lower = {c.lower(): c for c in df.columns}
    mapping = {}

    candidates = {
        'open': ['open', 'o'],
        'high': ['high', 'h'],
        'low': ['low', 'l'],
        'close': ['close', 'c']
    }

    for key, opts in candidates.items():
        found = None
        for opt in opts:
            if opt in lower:
                found = lower[opt]
                break
        if not found:
            for name_lower, original in lower.items():
                if key in name_lower:
                    found = original
                    break

        mapping[key] = found

    return mapping


def calculate_adx(input_df):
    """
    EXACT Excel-matching ADX calculation.
    """
    df = input_df.copy()

    # Detect OHLC columns
    ohlc_map = detect_ohlc_columns(df)

    if None in ohlc_map.values():
        missing = [k for k, v in ohlc_map.items() if v is None]
        raise ValueError("Missing OHLC columns: " + ", ".join(missing))

    # Determine date column (first column if not OHLC)
    first_col = df.columns[0]
    date_col = first_col if first_col not in ohlc_map.values() else None

    # Rename OHLC
    df = df.rename(columns={
        ohlc_map['open']: 'Open',
        ohlc_map['high']: 'High',
        ohlc_map['low']: 'Low',
        ohlc_map['close']: 'Close'
    })

    # Convert to numeric
    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(
        pd.to_numeric, errors='coerce'
    )

    # Previous values
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    # True Range
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

    # Excel behavior: first TR = blank
    df.loc[df.index[0], 'TR'] = np.nan

    # Directional Movement calculations
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    # ---------------------------------------------------------
    #  ⭐ FIXED DM LOGIC — EXACT SAME AS EXCEL ⭐
    # ---------------------------------------------------------
    # First row = blank
    df.loc[df.index[0], ['+DM 1', '-DM 1']] = np.nan

    # Next rows:
    # DM > 0 → value
    # DM <= 0 → ZERO (Excel shows 0, not blank)
    df['+DM 1'] = np.where(
        (df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0),
        df['UpMove'],
        0
    )

    df['-DM 1'] = np.where(
        (df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0),
        df['DownMove'],
        0
    )
    # ---------------------------------------------------------

    # Wilder smoothing
    N = 14
    df['TR14'] = wilder_sum_excel_style(df['TR'], N)
    df['+DM14'] = wilder_sum_excel_style(df['+DM 1'], N)
    df['-DM14'] = wilder_sum_excel_style(df['-DM 1'], N)

    # DI values
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    # DI diff & sum
    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    # DX
    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    # ADX smoothing (Excel exact)
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

    # Round everything
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].round(4)

    # Prepare output column order
    final_cols = []

    if date_col is not None:
        final_cols.append(date_col)
        df[date_col] = df[date_col].astype(str)

    final_cols += [
        'Open', 'High', 'Low', 'Close',
        'TR', '+DM 1', '-DM 1',
        'TR14', '+DM14', '-DM14',
        '+DI14', '-DI14',
        'DI 14 Diff', 'DI 14 Sum',
        'DX', 'ADX'
    ]

    present_cols = [c for c in final_cols if c in df.columns]

    return df[present_cols]
