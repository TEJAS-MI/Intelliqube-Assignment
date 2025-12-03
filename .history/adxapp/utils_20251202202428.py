# adxapp/utils.py

import pandas as pd
import numpy as np


def wilder_sum(series, n):
    """
    Wilder Smoothing EXACTLY as in Excel:
    row n = SUM of first n values
    row n+1 onward = prev - (prev/n) + today
    """
    result = [np.nan] * len(series)

    if len(series) < n:
        return result

    initial = series[:n].sum()
    result[n - 1] = initial

    for i in range(n, len(series)):
        prev = result[i - 1]
        result[i] = prev - (prev / n) + series[i]

    return result


def calculate_adx(df):
    """
    EXACT Assignment ADX Calculation (Excel-matching)
    """

    N = 14

    # Convert numeric fields
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

    # Directional Movement
    df['UpMove'] = df['High'] - df['Prev_High']
    df['DownMove'] = df['Prev_Low'] - df['Low']

    df['+DM 1'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], 0)
    df['-DM 1'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], 0)

    # Wilder Smoothing
    df['TR14'] = wilder_sum(df['TR'], N)
    df['+DM14'] = wilder_sum(df['+DM 1'], N)
    df['-DM14'] = wilder_sum(df['-DM 1'], N)

    # DI values
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100

    # DI difference and sum
    df['DI 14 Diff'] = (df['+DI14'] - df['-DI14']).abs()
    df['DI 14 Sum'] = df['+DI14'] + df['-DI14']

    # DX
    df['DX'] = (df['DI 14 Diff'] / df['DI 14 Sum']) * 100

    # ADX - Initial value at row 29 (index 27)
    adx = [np.nan] * len(df)
    start = N - 1
    end = (2 * N) - 2

    if len(df) > end:
        initial_adx = df['DX'][start:end + 1].mean()
        adx[end] = initial_adx

        # Wilder Smoothing for ADX
        for i in range(end + 1, len(df)):
            adx[i] = ((adx[i - 1] * (N - 1)) + df['DX'][i]) / N

    df['ADX'] = adx

    # Final output
    final_cols = [
        'Close', 'TR', '+DM 1', '-DM 1',
        'TR14', '+DM14', '-DM14',
        '+DI14', '-DI14',
        'DI 14 Diff', 'DI 14 Sum',
        'DX', 'ADX'
    ]

    return df[final_cols].round(4)
