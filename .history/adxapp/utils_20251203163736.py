# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum_excel_style(series, n):
    result = pd.Series([np.nan] * len(series), index=series.index)
    if len(series) <= n:
        return result
    arr = series.values

    # Excel initial sum = SUM rows 2..15 (skip row1)
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
            for name_lower, orig in lower.items():
                if key in name_lower:
                    found = orig
                    break
        mapping[key] = found

    return mapping


def calculate_adx(input_df):

    df = input_df.copy()

    # Detect and rename OHLC columns
    ohlc_map = detect_ohlc_columns(df)
    if None in ohlc_map.values():
        missing = [k for k, v in ohlc_map.items() if v is None]
        raise ValueError("Missing OHLC columns: " + ", ".join(missing))

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

    # True Range
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1', 'TR2', 'TR3']].max(axis=1)

    df.loc[df.index[0], 'TR'] = np.nan  # Excel style

    # Directional Movement
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where(
        (df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0),
        df['UpMove'],
        np.nan
    )

    df['-DM 1'] = np.where(
        (df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0),
        df['DownMove'],
        np.nan
    )

    # >>> FIX: Row-3 zeros (Excel style)
   

    N = 14

    # Wilder smoothing
    df['TR14'] = wilder_sum_excel_style(df['TR'], N)
    df['+DM14'] = wilder_sum_excel_style(df['+DM 1'].fillna(0), N)
    df['-DM14'] = wilder_sum_excel_style(df['-DM 1'].fillna(0), N)

    # DI
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    adx = pd.Series([np.nan] * len(df), index=df.index)

    start = N
    end = 2 * N - 1

    if len(df) > end:
        initial = df['DX'].iloc[start:end+1].mean()
        adx.iloc[end] = initial

        for i in range(end+1, len(df)):
            adx.iloc[i] = ((adx.iloc[i-1] * (N - 1)) + df['DX'].iloc[i]) / N

    df['ADX'] = adx

    # Keep numeric DataFrame for plotting
    df_numeric = df.copy()

    # DISPLAY DataFrame formatting (for CSV + HTML table)
    df_display = df.copy()

    # Format all numeric columns EXCEPT ADX
    num_cols = df_display.select_dtypes(include=[np.number]).columns
    for col in num_cols:
        if col != "ADX":
            df_display[col] = df_display[col].apply(
                lambda x: f"{x:.2f}" if pd.notna(x) else ""
            )

    # ADX stays raw (full precision)
    df_display["ADX"] = df_numeric["ADX"]

    # Final ordering
    cols = []
    if date_col:
        cols.append(date_col)
        df_display[date_col] = df_display[date_col].astype(str)

    cols += [
        'Open', 'High', 'Low', 'Close',
        'TR', '+DM 1', '-DM 1',
        'TR14', '+DM14', '-DM14',
        '+DI14', '-DI14',
        'DI 14 Diff', 'DI 14 Sum',
        'DX', 'ADX'
    ]

    df_display = df_display[cols]
    df_numeric = df_numeric[cols]

    return df_numeric, df_display
