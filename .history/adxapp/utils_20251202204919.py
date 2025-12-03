# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum(series, n):
    """Wilder smoothing that exactly matches the Excel approach."""
    result = [np.nan] * len(series)
    if len(series) < n:
        return result
    initial = series[:n].sum()
    result[n - 1] = initial
    for i in range(n, len(series)):
        prev = result[i - 1]
        result[i] = prev - (prev / n) + series[i]
    return result


def _find_ohlc_columns(df):
    """
    Return a mapping of canonical names to actual df column names.
    Handles case differences and common header variants.
    """
    cols_lower = {c.lower(): c for c in df.columns}
    mapping = {}

    # Common names for each field
    candidates = {
        'open': ['open', 'o'],
        'high': ['high', 'h'],
        'low': ['low', 'l'],
        'close': ['close', 'c']
    }

    for key, toks in candidates.items():
        found = None
        for t in toks:
            if t in cols_lower:
                found = cols_lower[t]
                break
        if not found:
            # try more generous match
            for name_lower, orig in cols_lower.items():
                if key in name_lower:
                    found = orig
                    break
        mapping[key] = found

    return mapping


def calculate_adx(df):
    """
    Returns a DataFrame with columns exactly matching the assignment solution,
    and preserves a Date/Time column (if present).
    """

    N = 14

    # Make a copy so we don't mutate the caller's df
    df = df.copy()

    # Detect if first column looks like a date/time or index to preserve.
    date_col = None
    if len(df.columns) > 4:
        # if there are more than four columns, assume first is Date/Time (common case)
        first_col = df.columns[0]
        # Heuristic: if first column is not an OHLC column, treat it as date/time to preserve
        ohlc_map = _find_ohlc_columns(df)
        if first_col not in ohlc_map.values():
            date_col = first_col

    # Find OHLC columns (case-insensitive). If names differ, try to detect.
    ohlc_map = _find_ohlc_columns(df)
    if None in ohlc_map.values():
        missing = [k for k, v in ohlc_map.items() if v is None]
        raise ValueError(f"Missing required columns in input CSV: {missing}. Make sure file has Open,High,Low,Close headers.")

    # Canonicalize names: create standard columns 'Open','High','Low','Close'
    df = df.rename(columns={
        ohlc_map['open']: 'Open',
        ohlc_map['high']: 'High',
        ohlc_map['low']: 'Low',
        ohlc_map['close']: 'Close'
    })

    # Convert numeric
    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(pd.to_numeric, errors='coerce')

    # Shifted previous values
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    # TR components and TR
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

    # Directional Movement (+DM1, -DM1)
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], 0.0)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], 0.0)

    # Wilder smoothing for TR14 and DM14 (Excel method)
    df['TR14'] = wilder_sum(df['TR'], N)
    df['+DM14'] = wilder_sum(df['+DM 1'], N)
    df['-DM14'] = wilder_sum(df['-DM 1'], N)

    # DI14 values
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    # DI diff and sum
    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    # DX
    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    # ADX (initial at index end = 2*N - 2)
    adx = [np.nan] * len(df)
    start = N - 1
    end = 2 * N - 2
    if len(df) > end:
        initial_adx = df['DX'][start:end + 1].mean()
        adx[end] = initial_adx
        for i in range(end + 1, len(df)):
            adx[i] = ((adx[i - 1] * (N - 1)) + df['DX'][i]) / N
    df['ADX'] = adx

    # Round numeric columns
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].round(4)

    # Build final column order — include date if present
    final_cols = []
    if date_col:
        # keep the original date column name
        final_cols.append(date_col)
        # ensure the date column remains unchanged (string or datetime)
        df[date_col] = df[date_col].astype(str)

    # Append OHLC & expected columns in exact order expected by assignment
    final_cols += [
        'Open', 'High', 'Low', 'Close',
        'TR', '+DM 1', '-DM 1',
        'TR14', '+DM14', '-DM14',
        '+DI14', '-DI14',
        'DI 14 Diff', 'DI 14 Sum',
        'DX', 'ADX'
    ]

    # Some notebooks/sheets show 'Close' at column E; Excel solution had Date + Open/High/Low/Close before TR.
    # If any final column is missing due to calculation (NaNs), keep it but don't fail.
    final_present = [c for c in final_cols if c in df.columns]

    return df[final_present]
