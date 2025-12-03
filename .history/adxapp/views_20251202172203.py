# Create your views here.
import io
import base64
import numpy as np
import pandas as pd

import matplotlib  #
matplotlib.use('Agg')     # Use non-GUI backend to avoid thread errors
from matplotlib import pyplot as plt

from django.shortcuts import render
from django.http import HttpResponse


def index(request):
    """Display the file upload page."""
    return render(request, 'adxapp/index.html')


def process_file(request):
    """
    Handle the uploaded CSV, compute ADX values,
    generate the plot and return the results page.
    """
    if request.method != "POST" or 'csv_file' not in request.FILES:
        return render(request, 'adxapp/index.html')

    uploaded_file = request.FILES['csv_file']

    # Read input CSV
    try:
        data = pd.read_csv(uploaded_file)
    except Exception:
        return HttpResponse("Unable to read CSV file. Please upload a valid file.")

    # Normalize column names
    data.columns = [c.strip().lower() for c in data.columns]

    if not {'open', 'high', 'low', 'close'}.issubset(data.columns):
        return HttpResponse("CSV must contain Open, High, Low, Close columns.")

    # Convert to float
    high = data['high'].astype(float)
    low = data['low'].astype(float)
    close = data['close'].astype(float)

    # Previous values
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    # True Range
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = np.vstack([tr1, tr2, tr3]).max(axis=0)

    # Directional Movements
    up_move = high - prev_high
    down_move = prev_low - low

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    data['tr'] = tr
    data['plus_dm'] = plus_dm
    data['minus_dm'] = minus_dm

    # Wilder smoothing
    period = 14

    def wilder_smooth(series, n):
        smoothed = [np.nan] * len(series)
        if len(series) < n:
            return smoothed
        initial = series[:n].sum()
        smoothed[n - 1] = initial
        for i in range(n, len(series)):
            previous = smoothed[i - 1]
            smoothed[i] = previous - (previous / n) + series[i]
        return smoothed

    data['tr_smooth'] = wilder_smooth(data['tr'], period)
    data['plus_dm_smooth'] = wilder_smooth(data['plus_dm'], period)
    data['minus_dm_smooth'] = wilder_smooth(data['minus_dm'], period)

    # DIs
    data['plus_di'] = (data['plus_dm_smooth'] / data['tr_smooth']) * 100
    data['minus_di'] = (data['minus_dm_smooth'] / data['tr_smooth']) * 100

    # DX
    data['dx'] = ((data['plus_di'] - data['minus_di']).abs() /
                  (data['plus_di'] + data['minus_di'])) * 100

    # ADX calculation
    adx = [np.nan] * len(data)

    start = period - 1
    end = 2 * period - 2

    if len(data) > end:
        initial_adx = data['dx'][start:end + 1].mean()
        adx[end] = initial_adx

        # Wilder smoothing
        for i in range(end + 1, len(data)):
            prev_val = adx[i - 1]
            adx[i] = ((prev_val * (period - 1)) + data['dx'][i]) / period

    data['adx'] = adx

    # Round values
    numeric_columns = data.select_dtypes(include=[np.number]).columns
    data[numeric_columns] = data[numeric_columns].round(4)

    # Save final CSV in session memory
    buffer = io.StringIO()
    data.to_csv(buffer, index=False)
    request.session['csv_output'] = buffer.getvalue()

    # Plot graph
    plt.figure(figsize=(10, 4))
    plt.plot(data['adx'], label='ADX')
    plt.plot(data['plus_di'], label='+DI')
    plt.plot(data['minus_di'], label='-DI')
    plt.title("ADX, +DI, -DI")
    plt.legend()
    plt.tight_layout()

    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    plt.close()
    img_stream.seek(0)

    graph_base64 = base64.b64encode(img_stream.read()).decode('utf-8')

    # Preview first 10 rows
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
    """Download the calculated CSV as a file."""
    csv_data = request.session.get('csv_output')

    if not csv_data:
        return HttpResponse("No calculated file available. Please upload a CSV first.")

    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=adx_output.csv'
    return response
