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
        return render(request, 'adxapp/index.html', {'error': "Please upload a CSV file."})

    uploaded_file = request.FILES['csv_file']

    try:
        # Read CSV normally (do NOT set index_col)
        df = pd.read_csv(uploaded_file)

        # Run ADX calculation (Excel-matching)
        result_df = calculate_adx(df)

    except Exception as e:
        return render(request, 'adxapp/index.html', {'error': f"Error: {e}"})

    # Save output in session for download
    csv_buffer = io.StringIO()
    result_df.to_csv(csv_buffer, index=False)
    request.session['csv_output'] = csv_buffer.getvalue()

    # ---- PLOT ----
    plt.figure(figsize=(10, 5))
    plt.plot(result_df['ADX'], label='ADX')
    plt.plot(result_df['+DI14'], label='+DI14')
    plt.plot(result_df['-DI14'], label='-DI14')
    plt.title("ADX, +DI14, -DI14")
    plt.legend()
    plt.tight_layout()

    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    plt.close()
    img_stream.seek(0)

    plot_base64 = base64.b64encode(img_stream.read()).decode()

    # ---- TABLE PREVIEW ----
    preview_df = result_df.head(10)

    return render(request, 'adxapp/result.html', {
        'plot_base64': plot_base64,
        'preview_columns': preview_df.columns.tolist(),
        'preview_data': preview_df.values.tolist()
    })


def download_csv(request):

    csv_data = request.session.get('csv_output')

    if not csv_data:
        return HttpResponse("No output to download. Upload a file first.")

    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="adx_output.csv"'

    return response
