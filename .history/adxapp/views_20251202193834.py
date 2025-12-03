import io
import base64
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt

from django.shortcuts import render
from django.http import HttpResponse


def index(request):
    return render(request, 'adxapp/index.html')


def process_file(request):

    if request.method != "POST" or 'csv_file' not in request.FILES:
        return render(request, 'adxapp/index.html')

    uploaded_file = request.FILES['csv_file']

    # Read CSV
    try:
        data = pd.read_csv(uploaded_file)
    except Exception:
        return HttpResponse("Unable to read CSV file. Please upload a valid CSV.")

    # Normalize headers
    data.columns = [c.strip().lower() for c in data.columns]

    required = {'open', 'high', 'low', 'close'}
    if not required.issubset(data.columns):
        return HttpResponse("CSV must contain Open, High, Low, Close columns.")

    # Convert OHLC to float
    high = data['high'].astype(float)
    low = data['low'].astype(float)
    close = data['close'].astype(float)

    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    # TRUE RANGE
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = np.vstack([tr1, tr2, tr3]).max(axis=0)

    # DIRECTIONAL MOVEMENTS (+DM1, -DM1)
    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    data['TR'] = tr
    data['+DM 1'] = plus_dm
    data['-DM 1'] = minus_dm

    period = 14

    # WILDER SUM FUNCTION (Matches assignment exactly)
    def wilder_sum(series, n):
        result = [np.nan] * len(series)
        if len(series) < n:
            return result

        initial = series[:n].sum()      # Row 16 in Excel
        result[n - 1] = initial

        for i in range(n, len(series)):
            prev = result[i - 1]
            result[i] = prev - (prev / n) + series[i]

        return result

    # SMOOTHED VALUES
    data['TR14'] = wilder_sum(data['TR'], period)
    data['+DM14'] = wilder_sum(data['+DM 1'], period)
    data['-DM14'] = wilder_sum(data['-DM 1'], period)

    # DI CALCULATIONS
    data['+DI14'] = (data['+DM14'] / data['TR14']) * 100
    data['-DI14'] = (data['-DM14'] / data['TR14']) * 100

    # DI DIFFERENCE & SUM (Excel Columns N & O)
    data['DI 14 Diff'] = (data['+DI14'] - data['-DI14']).abs()
    data['DI 14 Sum'] = data['+DI14'] + data['-DI14']

    # DX (Excel Column P)
    data['DX'] = (data['DI 14 Diff'] / data['DI 14 Sum']) * 100

    # ADX (Excel Column Q)
    adx = [np.nan] * len(data)
    start = period - 1       # 13
    end = (2 * period) - 2   # 27 (Excel row 29)

    if len(data) > end:
        initial_adx = data['DX'][start:end + 1].mean()
        adx[end] = initial_adx

        for i in range(end + 1, len(data)):
            adx[i] = ((adx[i - 1] * (period - 1)) + data['DX'][i]) / period

    data['ADX'] = adx

    # ROUND ALL NUMBER COLUMNS
    num_cols = data.select_dtypes(include=[np.number]).columns
    data[num_cols] = data[num_cols].round(4)

    # REORDER COLUMNS TO MATCH ASSIGNMENT EXACTLY
    final_cols = [
        'close',
        'TR',
        '+DM 1',
        '-DM 1',
        'TR14',
        '+DM14',
        '-DM14',
        '+DI14',
        '-DI14',
        'DI 14 Diff',
        'DI 14 Sum',
        'DX',
        'ADX'
    ]

    data = data[final_cols]

    # SAVE OUTPUT IN SESSION
    buffer = io.StringIO()
    data.to_csv(buffer, index=False)
    request.session['csv_output'] = buffer.getvalue()

    # PLOT
    plt.figure(figsize=(10, 4))
    plt.plot(data['ADX'], label='ADX')
    plt.plot(data['+DI14'], label='+DI14')
    plt.plot(data['-DI14'], label='-DI14')
    plt.title("ADX, +DI14, -DI14")
    plt.legend()
    plt.tight_layout()

    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    plt.close()
    img_stream.seek(0)

    graph_base64 = base64.b64encode(img_stream.read()).decode()

    preview = data.head(10)

    return render(
        request,
        'adxapp/result.html',
        {
            'plot_base64': graph_base64,
            'preview_columns': list(preview.columns),
            'preview_data': preview.values.tolist()
        }
    )


def download_csv(request):
    csv_data = request.session.get('csv_output')
    if not csv_data:
        return HttpResponse("No calculated file available. Upload a CSV first.")

    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=adx_output.csv'
    return response
