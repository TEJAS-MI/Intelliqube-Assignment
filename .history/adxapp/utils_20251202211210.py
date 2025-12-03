# adxapp/utils.py

import pandas as pd
import numpy as np

def wilder_sum(series, n):
    """
    Wilder smoothing that exactly matches Excel-style:
    - index (n-1) = sum(series[0:n])
    - from n onward: prev - (prev / n) + current
    """
    result = [np.nan] * len(series)
    if len(series) < n:
        return result
    # Use .values to avoid alignment surprises
    arr = series.values
    initial = np.nansum(arr[:n])
    result[n - 1] = initial
    for i in range(n, len(arr)):
        prev = result[i - 1]
        # If prev is NaN (shouldn't be after n-1) keep formula safe
        if np.isnan(prev):
            result[i] = np.nan
        else:
            result[i] = prev - (prev / n) + arr[i]
    return pd.Series(result, index=series.index)


def detect_ohlc_columns(df):
    """
    Return mapping for open/high/low/close using case-insensitive matching.
    Returns dict: {'open':colname, 'high':..., 'low':..., 'close':...}
    """
    lower = {c.lower(): c for c in df.columns}
    mapping = {}
    for key in ('open', 'high', 'low', 'close'):
        found = None
        # direct exact names
        for candidate in (key, key[0]):  # 'open' and 'o'
            if candidate in lower:
                found = lower[candidate]
                break
        # looser search
        if not found:
            for name_lower, orig in lower.items():
                if key in name_lower:
                    found = orig
                    break
        mapping[key] = found
    return mapping


def calculate_adx(input_df):
    """
    Calculate ADX matching the assignment Excel exactly.
    Expects input_df with a Date/Time column (kept as-is) and OHLC columns.
    Returns DataFrame with columns in exact order:
    [Date?, Open, High, Low, Close, TR, +DM 1, -DM 1, TR14, +DM14, -DM14,
     +DI14, -DI14, DI 14 Diff, DI 14 Sum, DX, ADX]
    """
    df = input_df.copy()

    # Detect if first column is date/time (i.e., not an OHLC column)
    first_col = df.columns[0]
    ohlc_map = detect_ohlc_columns(df)

    # If any OHLC missing -> raise helpful error
    if None in ohlc_map.values():
        missing = [k for k, v in ohlc_map.items() if v is None]
        raise ValueError("Missing OHLC columns in input CSV: " + ", ".join(missing))

    # If first_col is not one of the OHLC real columns, keep it as date_col
    date_col = None
    if first_col not in ohlc_map.values():
        date_col = first_col
        # preserve date column as-is (string / datetime) - do not convert now

    # Rename OHLC columns to canonical names
    df = df.rename(columns={
        ohlc_map['open']: 'Open',
        ohlc_map['high']: 'High',
        ohlc_map['low']: 'Low',
        ohlc_map['close']: 'Close'
    })

    # Convert OHLC numeric
    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(
        pd.to_numeric, errors='coerce'
    )

    # Create previous columns
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    # True Range components
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()

    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

    # Directional movements (+DM 1, -DM 1)
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], 0.0)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], 0.0)

    # Wilder smoothing (sum-based) for TR14, +DM14, -DM14
    N = 14
    df['TR14'] = wilder_sum(df['TR'], N)
    df['+DM14'] = wilder_sum(df['+DM 1'], N)
    df['-DM14'] = wilder_sum(df['-DM 1'], N)

    # DI calculations
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    # DI diff and sum
    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    # DX
    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    # ADX initial and smoothing (Excel-style)
    adx = [np.nan] * len(df)
    start = N - 1            # 13
    end = 2 * N - 2          # 27
    if len(df) > end:
        # average DX from index start .. end inclusive
        # use .iloc to avoid label/index confusion
        initial_adx = df['DX'].iloc[start:end + 1].mean()
        adx[end] = initial_adx
        for i in range(end + 1, len(df)):
            adx[i] = ((adx[i - 1] * (N - 1)) + df['DX'].iloc[i]) / N
    df['ADX'] = adx

    # Round numeric columns same as Excel
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].round(4)

    # Build final column list, preserving date col if present
    final_cols = []
    if date_col is not None:
        final_cols.append(date_col)
        # Ensure date column converted to string (Excel shows date/time strings)
        df[date_col] = df[date_col].astype(str)

    final_cols += [
        'Open', 'High', 'Low', 'Close',
        'TR', '+DM 1', '-DM 1',
        'TR14', '+DM14', '-DM14',
        '+DI14', '-DI14',
        'DI 14 Diff', 'DI 14 Sum',
        'DX', 'ADX'
    ]

    # Keep only columns that exist (safer) and return
    present_cols = [c for c in final_cols if c in df.columns]
    return df[present_cols]
