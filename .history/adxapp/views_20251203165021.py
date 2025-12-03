views.py
# adxapp/views.py

import pandas as pd
from django.shortcuts import render
from django.http import HttpResponse
from .utils import calculate_adx
import matplotlib
matplotlib.use('Agg')
from matplotlib import pyplot as plt
import io
import base64


def index(request):
    return render(request, 'adxapp/index.html')


def process_file(request):
    if request.method != 'POST':
        return render(request, 'adxapp/index.html')

    if 'csv_file' not in request.FILES:
        return render(request, 'adxapp/index.html', {'error': 'Please upload a CSV file.'})

    uploaded_file = request.FILES['csv_file']

    try:
        # Read the CSV exactly as-is (do not set index_col)
        df_in = pd.read_csv(uploaded_file)
        # Calculate ADX (utils will detect date and OHLC)
        result_df = calculate_adx(df_in)
    except Exception as e:
        return render(request, 'adxapp/index.html', {'error': f'Error processing file: {e}'})

    # Save result CSV in session for download
    csv_buffer = io.StringIO()
    result_df.to_csv(csv_buffer, index=False)
    request.session['csv_output'] = csv_buffer.getvalue()

    # Produce plot: plot numeric arrays (skip NaNs automatically)
    plt.figure(figsize=(10, 5))
    # plot by column values so x-axis is simple index (Excel comparison is by values)
    plt.plot(result_df['ADX'].values, label='ADX')
    plt.plot(result_df['+DI14'].values, label='+DI14')
    plt.plot(result_df['-DI14'].values, label='-DI14')
    plt.title('ADX, +DI14, -DI14')
    plt.legend()
    plt.tight_layout()

    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png')
    plt.close()
    img_buffer.seek(0)
    plot_base64 = base64.b64encode(img_buffer.read()).decode('utf-8')

    # Prepare preview including date column if present
    preview_df = result_df.head(10)
    preview_columns = preview_df.columns.tolist()
    preview_data = preview_df.values.tolist()

    return render(request, 'adxapp/result.html', {
        'plot_base64': plot_base64,
        'preview_columns': preview_columns,
        'preview_data': preview_data
    })


def download_csv(request):
    csv_data = request.session.get('csv_output')
    if not csv_data:
        return HttpResponse("No output to download. Upload and process a file first.", status=400)
    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="adx_output.csv"'
    return response