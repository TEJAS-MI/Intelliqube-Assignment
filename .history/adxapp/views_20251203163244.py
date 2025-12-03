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
        df_in = pd.read_csv(uploaded_file)

        # GET BOTH VERSIONS
        df_numeric, df_display = calculate_adx(df_in)

    except Exception as e:
        return render(
            request,
            'adxapp/index.html',
            {'error': f'Error processing file: {e}'}
        )

    # Save CSV (DISPLAY VERSION)
    csv_buffer = io.StringIO()
    df_display.to_csv(csv_buffer, index=False)
    request.session['csv_output'] = csv_buffer.getvalue()

    # Plot using df_numeric (real floats)
    plt.figure(figsize=(10, 5))
    plt.plot(df_numeric['ADX'].values, label='ADX')
    plt.plot(df_numeric['+DI14'].values, label='+DI14')
    plt.plot(df_numeric['-DI14'].values, label='-DI14')
    plt.legend()
    plt.title("ADX, +DI14, -DI14")
    plt.tight_layout()

    img = io.BytesIO()
    plt.savefig(img, format='png')
    plt.close()
    img.seek(0)
    plot_base64 = base64.b64encode(img.read()).decode('utf-8')

    preview_df = df_display.head(10)
    return render(
        request,
        'adxapp/result.html',
        {
            'plot_base64': plot_base64,
            'preview_columns': preview_df.columns.tolist(),
            'preview_data': preview_df.values.tolist()
        }
    )


def download_csv(request):
    csv_data = request.session.get('csv_output')
    if not csv_data:
        return HttpResponse("No output to download.", status=400)

    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename=\"adx_output.csv\"'
    return response
