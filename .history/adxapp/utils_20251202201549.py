# adxapp/utils.py

import pandas as pd
import numpy as np

def calculate_adx(df):
    """
    Calculates the Average Directional Index (ADX) using N=14 and Wilder's Smoothing.
    """
    N = 14 # Lookback period

    # --- 1. Data Preparation and Shift ---
    df.iloc[:, 0:] = df.iloc[:, 0:].apply(pd.to_numeric, errors='coerce') 
    
    df['Prev_Close'] = df['Close'].shift(1)
    df['Prev_High'] = df['High'].shift(1)
    df['Prev_Low'] = df['Low'].shift(1)

    df = df.dropna(subset=['Prev_Close']).copy()

    # --- 2. True Range (TR) ---
    df['H-L'] = df['High'] - df['Low']
    df['H-PC'] = abs(df['High'] - df['Prev_Close'])
    df['L-PC'] = abs(df['Low'] - df['Prev_Close'])
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)

    # --- 3. Directional Movement (DM) ---
    df['+DM_Raw'] = np.where(
        (df['High'] - df['Prev_High']) > (df['Prev_Low'] - df['Low']),
        np.maximum(df['High'] - df['Prev_High'], 0),
        0
    )
    df['-DM_Raw'] = np.where(
        (df['Prev_Low'] - df['Low']) > (df['High'] - df['Prev_High']),
        np.maximum(df['Prev_Low'] - df['Low'], 0),
        0
    )
    
    # --- 4. Smoothed TR and DM (Wilder's Smoothing using EWM) ---
    df['TR14'] = df['TR'].ewm(span=N, adjust=False).mean()
    df['+DM14'] = df['+DM_Raw'].ewm(span=N, adjust=False).mean()
    df['-DM14'] = df['-DM_Raw'].ewm(span=N, adjust=False).mean()

    # --- 5. Directional Indicators (DI) ---
    df['+DI14'] = (df['+DM14'] / df['TR14']) * 100
    df['-DI14'] = (df['+DM14'] / df['TR14']) * 100
    
    # Correction: The -DI14 calculation was using +DM14. It should use -DM14.
    df['-DI14'] = (df['-DM14'] / df['TR14']) * 100 # FIX: Corrected calculation
    
    # Replace NaNs/Infs that occur from division by zero in the initial rows
    df[['+DI14', '-DI14']] = df[['+DI14', '-DI14']].replace([np.inf, -np.inf, np.nan], 0)

    # --- 6. DX ---
    df['DI_Diff'] = abs(df['+DI14'] - df['-DI14'])
    df['DI_Sum'] = df['+DI14'] + df['-DI14']
    
    df['DX'] = (df['DI_Diff'] / df['DI_Sum']) * 100
    df['DX'].replace([np.inf, -np.inf, np.nan], 0, inplace=True)

    # --- 7. ADX (Smoothed DX) ---
    df['ADX'] = df['DX'].ewm(span=N, adjust=False).mean()

    # --- 8. Final Formatting and Column Selection ---
    output_df = df.rename(columns={
        '+DM_Raw': '+DM 1', 
        '-DM_Raw': '-DM 1', 
        'DI_Diff': 'DI 14 Diff', 
        'DI_Sum': 'DI 14 Sum'
    })
    
    final_cols = [
        'Open', 'High', 'Low', 'Close', 
        'TR', '+DM 1', '-DM 1', 
        'TR14', '+DM14', '-DM14', 
        '+DI14', '-DI14', 
        'DI 14 Diff', 'DI 14 Sum', 'DX', 'ADX'
    ]
    
    return output_df[final_cols]