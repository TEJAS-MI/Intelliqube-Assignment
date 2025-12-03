import pandas as pd
import numpy as np


def wilder_sum(series, n):
    result = [np.nan] * len(series)
    if len(series) < n:
        return result
    initial = series[:n].sum()
    result[n - 1] = initial
    for i in range(n, len(series)):
        prev = result[i - 1]
        result[i] = prev - (prev / n) + series[i]
    return result


def detect_ohlc_columns(df):
    mapping = {}
    lower = {c.lower(): c for c in df.columns}
    fields = {
        'open': ['open', 'o'],
        'high': ['high', 'h'],
        'low': ['low', 'l'],
        'close': ['close', 'c']
    }
    for key, opts in fields.items():
        found = None
        for o in opts:
            if o in lower:
                found = lower[o]
                break
        if not found:
            for c in lower:
                if key in c:
                    found = lower[c]
                    break
        mapping[key] = found
    return mapping


def calculate_adx(df):
    df = df.copy()

    # Detect DateTime column (kept exactly same as input)
    first_col = df.columns[0]
    datetime_col = first_col

    # Detect OHLC columns
    ohlc = detect_ohlc_columns(df)
    if None in ohlc.values():
        raise ValueError("Missing OHLC Columns")

    # Rename OHLC to fixed names
    df = df.rename(columns={
        ohlc['open']: 'Open',
        ohlc['high']: 'High',
        ohlc['low']: 'Low',
        ohlc['close']: 'Close'
    })

    df[['Open','High','Low','Close']] = df[['Open','High','Low','Close']].apply(pd.to_numeric, errors='coerce')

    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    # True Range
    df['TR1'] = df['High'] - df['Low']
    df['TR2'] = (df['High'] - df['Prev_Close']).abs()
    df['TR3'] = (df['Low'] - df['Prev_Close']).abs()
    df['TR'] = df[['TR1','TR2','TR3']].max(axis=1)

    # DM
    df['Up'] = df['High'] - df['Prev_High']
    df['Down'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where((df['Up'] > df['Down']) & (df['Up'] > 0), df['Up'], 0)
    df['-DM 1'] = np.where((df['Down'] > df['Up']) & (df['Down'] > 0), df['Down'], 0)

    # Wilder smoothing EXACT Excel
    N = 14
    df['TR14'] = wilder_sum(df['TR'], N)
    df['+DM14'] = wilder_sum(df['+DM 1'], N)
    df['-DM14'] = wilder_sum(df['-DM 1'], N)

    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    # ADX INITIAL = average of DX 14 values (rows 14–27)
    adx = [np.nan] * len(df)
    start = 13
    end = 27

    if len(df) > end:
        adx[end] = df['DX'][start:end+1].mean()
        for i in range(end+1, len(df)):
            adx[i] = ((adx[i-1] * 13) + df['DX'][i]) / 14

    df['ADX'] = adx

    numeric_cols = df.select_dtypes(include=[float,int]).columns
    df[numeric_cols] = df[numeric_cols].round(4)

    # Final column sequence EXACT
    final_cols = [
        datetime_col,
        'Open','High','Low','Close',
        'TR','+DM 1','-DM 1',
        'TR14','+DM14','-DM14',
        '+DI14','-DI14',
        'DI 14 Diff','DI 14 Sum',
        'DX','ADX'
    ]

    return df[final_cols]
