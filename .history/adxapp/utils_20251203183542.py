# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum_excel_style(series, n):
    """
    Implements Wilder's Summation exactly as required by the Excel solution.
    Initial sum is placed at index N, smoothing starts at N+1.
    """
    result = pd.Series([np.nan] * len(series), index=series.index)
    if len(series) <= n:
        return result

    arr = series.values
    
    # CRITICAL: Excel sum starts from index 1 (the first non-NaN TR/DM value) 
    # and sums N periods (up to index N), placing the sum at index N (row 15).
    initial_sum = np.nansum(arr[1:n+1])  
    result.iloc[n] = initial_sum

    # Smoothing starts from the N+1 position (index N+1, row 16)
    for i in range(n + 1, len(arr)):
        prev = result.iloc[i-1]
        if np.isnan(prev):
            # This should generally not happen if the input series is correctly prepared
            result.iloc[i] = np.nan
        else:
            # Wilder's Sum Formula: WS_t = WS_{t-1} - (WS_{t-1} / N) + Value_t
            result.iloc[i] = prev - (prev / n) + arr[i]

    return result


def detect_ohlc_columns(df):
    """Detects OHLC columns based on common names."""
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
    N = 14
    df = input_df.copy()
    
    # --- 0. Column Detection & Preparation ---
    ohlc_map = detect_ohlc_columns(df)
    if None in ohlc_map.values():
        missing = [k for k, v in ohlc_map.items() if v is None]
        raise ValueError("Missing OHLC columns in input CSV: " + ", ".join(missing))

    first_col = df.columns[0]
    date_col = first_col if first_col not in ohlc_map.values() else None

    df = df.rename(columns={
        ohlc_map['open']: 'Open', ohlc_map['high']: 'High', 
        ohlc_map['low']: 'Low', ohlc_map['close']: 'Close'
    })

    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(
        pd.to_numeric, errors='coerce'
    )
    
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    # --- 1. TR and DM Calculation ---
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
    df.loc[df.index[0], 'TR'] = np.nan # Excel keeps first row blank

    # DM (Directional Movement)
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    # Vectorized DM calculation: Set to 0.0 where DM is not positive and winning
    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], 0.0)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], 0.0)

    # Ensure the very first row is NaN for display consistency
    if len(df) >= 1:
        df.iloc[0, df.columns.get_loc('+DM 1')] = np.nan
        df.iloc[0, df.columns.get_loc('-DM 1')] = np.nan

    # --- 2. Smoothed TR and DM ---
    # NOTE: The wilder_sum_excel_style handles the specific index initialization.
    df['TR14'] = wilder_sum_excel_style(df['TR'].fillna(0), N)
    df['+DM14'] = wilder_sum_excel_style(df['+DM 1'].fillna(0), N)
    df['-DM14'] = wilder_sum_excel_style(df['-DM 1'].fillna(0), N)

    # --- 3. DI and DX Calculation ---
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100
    
    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']
    
    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100
    df['DX'] = df['DX'].replace([np.inf, -np.inf, np.nan], 0)

    # --- 4. ADX Calculation ---
    adx = pd.Series([np.nan] * len(df), index=df.index)

    # The first ADX value (Row 2N, index 2N-1) is the SMA of the previous N DX values (indices N to 2N-1).
    start = N
    end = 2 * N - 1

    if len(df) > end:
        # Initial value is the mean (SMA) of the N DX values
        adx.iloc[end] = df['DX'].iloc[start:end + 1].mean()
        
        # Subsequent values use Wilder's Smoothing
        for i in range(end + 1, len(df)):
            prev = adx.iloc[i - 1]
            adx.iloc[i] = ((prev * (N - 1)) + df['DX'].iloc[i]) / N

    df['ADX'] = adx

    # --- 5. Final Output Preparation ---

    # CRITICAL FIX: Removed intermediate rounding. 
    # Rounding only the final result to high precision (e.g., 6 decimal places).
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].round(6) 

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