# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum_excel_style(series, n):
    """
    Implements Wilder's Summation exactly as Excel does for TR14, +DM14, -DM14.
    The first N-1 calculated value (at index N-1) is the SUM of the first N raw values (indices 0 to N-1).
    Subsequent values use the recursive Wilder's formula.
    """
    result = pd.Series([np.nan] * len(series), index=series.index)
    if len(series) < n:
        return result
        
    arr = series.values

    # 1. Calculate the initial SUM (Indices 0 to N-1, total N periods)
    initial_sum = np.nansum(arr[0:n]) 
    
    # 2. Place the initial SUM value at index N-1 (This is the 14th visual row)
    result.iloc[n - 1] = initial_sum 

    # 3. Apply the recursive Wilder's Summation (EMA) from index N onward (15th visual row)
    for i in range(n, len(arr)):
        prev = result.iloc[i-1]
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

    # Detect the date column (it will be the first column if it's not an OHLC column)
    first_col = df.columns[0]
    date_col = first_col if first_col not in ohlc_map.values() else None

    df = df.rename(columns={
        ohlc_map['open']: 'Open', ohlc_map['high']: 'High', 
        ohlc_map['low']: 'Low', ohlc_map['close']: 'Close'
    })

    df[['Open', 'High', 'Low', 'Close']] = df[['Open', 'High', 'Low', 'Close']].apply(
        pd.to_numeric, errors='coerce'
    )
    
    # --- 1. TR and DM Calculation ---
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)
    # Note: We keep the first row (NaNs) here for correct Excel indexing alignment

    # True Range (TR)
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)
    
    # DM (Directional Movement)
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    # Vectorized DM calculation: Set to 0.0 where DM is not positive and winning
    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], 0.0)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], 0.0)
    
    # Excel starts TR/DM calculation on the second row. We set the first row back to NaN for display.
    if len(df) >= 1:
        for col in ['TR', '+DM 1', '-DM 1']:
            if col in df.columns:
                 df.iloc[0, df.columns.get_loc(col)] = np.nan

    # --- 2. Smoothed TR and DM (Using corrected wilder_sum_excel_style) ---
    # NOTE: The wilder_sum function handles the necessary fillna(0) for smoothing starting from the second row
    df['TR14'] = wilder_sum_excel_style(df['TR'].fillna(0), N)
    df['+DM14'] = wilder_sum_excel_style(df['+DM 1'], N)
    df['-DM14'] = wilder_sum_excel_style(df['-DM 1'], N)

    # --- 3. DI and DX Calculation ---
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100
    
    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']
    
    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100
    df['DX'] = df['DX'].replace([np.inf, -np.inf, np.nan], 0)

    # --- 4. ADX Calculation (Manual Initialization) ---
    adx = pd.Series([np.nan] * len(df), index=df.index)
    
    # DX values are valid starting from index N-1 (Row 14).
    # The first ADX value (Row 2N, index 2N-1) is the SMA of the previous N DX values (indices N to 2N-1).
    start_index_for_mean = N
    end_index_for_adx_init = 2 * N - 1 
    
    if len(df) > end_index_for_adx_init:
        # Calculate the SMA of the first N valid DX values (indices N to 2N-1)
        initial_adx = df['DX'].iloc[start_index_for_mean : end_index_for_adx_init + 1].mean()
        adx.iloc[end_index_for_adx_init] = initial_adx 
        
        # Continue with Wilder's Smoothing for subsequent values 
        for i in range(end_index_for_adx_init + 1, len(df)):
            prev = adx.iloc[i - 1]
            adx.iloc[i] = ((prev * (N - 1)) + df['DX'].iloc[i]) / N

    df['ADX'] = adx

    # --- 5. Final Output Preparation ---

    # *** CRITICAL FIX: NO INTERMEDIATE ROUNDING. ROUND ONLY THE FINAL OUTPUT FOR CLEANLINESS. ***
    # Rounding to 6 decimal places for final output consistency (Excel uses high precision).
    num_cols = df.select_dtypes(include=[np.number]).columns
    df[num_cols] = df[num_cols].round(6) 

    # Build final output column order
    final = []
    if date_col is not None:
        final.append(date_col)
        df[date_col] = df[date_col].astype(str) # Convert date to string for consistent CSV output

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