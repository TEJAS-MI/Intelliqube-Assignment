# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum_excel_style(series, n):
    """
    Excel-style Wilder smoothing used in the interviewer's sheet.

    Important differences from naive implementations:
    - The initial smoothed value is placed at index `n` (0-based)
      and is the SUM of series.iloc[1 : n+1] (i.e., skipping the first row).
    - From index n+1 onward apply: prev - (prev / n) + current
    """
    result = pd.Series([np.nan] * len(series), index=series.index)

    # If not enough rows, return all-NaN series (will appear as blank in CSV)
    if len(series) <= n:
        return result

    arr = series.values  # raw numpy array for index-based sums
    # Initial sum = sum of elements at positions 1..n inclusive (1-based offset)
    initial_sum = np.nansum(arr[1:n+1])  # sums arr[1]..arr[n]
    # Place initial_sum at index n (0-based)
    result.iloc[n] = initial_sum

    # Wilder smoothing forward from index n+1
    for i in range(n+1, len(arr)):
        prev = result.iloc[i-1]
        if np.isnan(prev):
            # Shouldn't happen after initial placement, but keep safe
            result.iloc[i] = np.nan
        else:
            result.iloc[i] = prev - (prev / n) + arr[i]

    return result


def detect_ohlc_columns(df):
    """
    Detect Open/High/Low/Close column names in a case-insensitive manner.
    Returns dict with keys 'open','high','low','close' and values = actual column names.
    """
    lower_map = {c.lower(): c for c in df.columns}
    mapping = {}
    # common candidates
    candidates = {
        'open': ['open', 'o'],
        'high': ['high', 'h'],
        'low': ['low', 'l'],
        'close': ['close', 'c']
    }
    for key, opts in candidates.items():
        found = None
        for opt in opts:
            if opt in lower_map:
                found = lower_map[opt]
                break
        if not found:
            # looser partial match
            for name_lower, orig in lower_map.items():
                if key in name_lower:
                    found = orig
                    break
        mapping[key] = found
    return mapping


def calculate_adx(input_df):
    """
    Calculate ADX matching the interviewer's Excel EXACTLY.
    Returns dataframe with columns (Date? if present), Open, High, Low, Close,
    TR, +DM 1, -DM 1, TR14, +DM14, -DM14, +DI14, -DI14, DI 14 Diff, DI 14 Sum, DX, ADX
    and blanks where Excel has blanks.
    """

    # Work on a copy
    df = input_df.copy()

    # Detect potential Date/Time column (first column that is NOT one of OHLC)
    candidates_map = detect_ohlc_columns(df)
    if None in candidates_map.values():
        missing = [k for k, v in candidates_map.items() if v is None]
        raise ValueError("Missing OHLC columns in input CSV: " + ", ".join(missing))

    first_col = df.columns[0]
    date_col = None
    if first_col not in candidates_map.values():
        date_col = first_col  # preserve original label

    # Rename OHLC to canonical names
    df = df.rename(columns={
        candidates_map['open']: 'Open',
        candidates_map['high']: 'High',
        candidates_map['low']: 'Low',
        candidates_map['close']: 'Close'
    })

    # Convert numbers
    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(
        pd.to_numeric, errors='coerce'
    )

    # Build previous fields
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    # TRUE RANGE (TR) components
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()

    # TR: maximum of the three components
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

    # IMPORTANT: Excel left the very first TR cell blank (not zero).
    # Ensure the first index has no TR value (so CSV cell is blank)
    if len(df) >= 1:
        df.loc[df.index[0], 'TR'] = np.nan

    # Directional Movements (+DM1, -DM1)
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], np.nan)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], np.nan)

    # Excel shows blanks (not zeros) for +DM1/-DM1 in the first row — keep as NaN so CSV writes blank.
    # (Later operations will produce numeric values where appropriate.)

    # Wilder sum (Excel-style) for TR14 and DM14
    N = 14
    # Use the function that places initial at index N (0-based),
    # computed as sum of series.iloc[1 : N+1]
    df['TR14'] = wilder_sum_excel_style(df['TR'], N)
    df['+DM14'] = wilder_sum_excel_style(df['+DM 1'].fillna(0), N)  # fillna(0) before sum as Excel treats blanks as 0 in sums
    df['-DM14'] = wilder_sum_excel_style(df['-DM 1'].fillna(0), N)

    # DI14 calculations
    # Use division that produces NaN where TR14 is NaN or zero
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    # DI diff and sum (Excel columns)
    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    # DX
    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    # ADX initialization: Excel's ADX initial is at index = 2*N - 1 (0-based).
    # ADX_initial = mean(DX.iloc[N : 2*N]) placed at index 2*N - 1.
    adx = pd.Series([np.nan] * len(df), index=df.index)
    start = N      # starting DX index for averaging (14)
    end = 2 * N - 1  # ADX initial index (27 for N=14)

    if len(df) > end:
        # Average DX from indices start .. end (inclusive)
        initial_adx = df['DX'].iloc[start:end + 1].mean()
        adx.iloc[end] = initial_adx
        # Wilder smoothing afterwards
        for i in range(end + 1, len(df)):
            prev = adx.iloc[i - 1]
            if pd.isna(prev):
                adx.iloc[i] = np.nan
            else:
                adx.iloc[i] = ((prev * (N - 1)) + df['DX'].iloc[i]) / N

    df['ADX'] = adx

    # Round numeric columns to 4 decimals (Excel-style)
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].round(4)

    # Build final column order, preserving date column if present
    final_cols = []
    if date_col is not None:
        final_cols.append(date_col)
        # ensure date column is string so CSV shows same text as input
        df[date_col] = df[date_col].astype(str)

    final_cols += [
        'Open', 'High', 'Low', 'Close',
        'TR', '+DM 1', '-DM 1',
        'TR14', '+DM14', '-DM14',
        '+DI14', '-DI14',
        'DI 14 Diff', 'DI 14 Sum',
        'DX', 'ADX'
    ]

    # Keep only present columns (safer if input lacked some helpers)
    present = [c for c in final_cols if c in df.columns]
    return df[present]
