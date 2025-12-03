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
        # Read CSV without forcing index_col — keep the original date/time column if present
        df = pd.read_csv(uploaded_file)

        # Execute the Excel-matching ADX calculation
        result_df = calculate_adx(df)

    except Exception as e:
        return render(request, 'adxapp/index.html', {'error': f"Error processing file: {e}"})

    # Save CSV in session for download
    csv_buffer = io.StringIO()
    result_df.to_csv(csv_buffer, index=False)
    request.session['csv_output'] = csv_buffer.getvalue()

    # Create plot (skip initial NaNs)
    plt.figure(figsize=(10, 5))
    # Plot ADX and DIs — only numerical arrays to avoid plotting date strings directly
    plt.plot(result_df['ADX'].values, label='ADX')
    plt.plot(result_df['+DI14'].values, label='+DI14')
    plt.plot(result_df['-DI14'].values, label='-DI14')
    plt.title("ADX, +DI14, -DI14")
    plt.legend()
    plt.tight_layout()

    img_stream = io.BytesIO()
    plt.savefig(img_stream, format='png')
    plt.close()
    img_stream.seek(0)
    plot_base64 = base64.b64encode(img_stream.read()).decode()

    # Prepare preview (first 10 rows). If date column exists it will be included as first column.
    preview_df = result_df.head(10)
    preview_df_display = preview_df.copy()
    # Convert any non-string date column to string for safe rendering
    if preview_df_display.columns[0] not in ['Open', 'High', 'Low', 'Close', 'TR']:
        # assume first col is date/time and keep as string
        preview_df_display.iloc[:, 0] = preview_df_display.iloc[:, 0].astype(str)

    context = {
        'plot_base64': plot_base64,
        'preview_columns': preview_df_display.columns.tolist(),
        'preview_data': preview_df_display.values.tolist()
    }
    return render(request, 'adxapp/result.html', context)


def download_csv(request):
    csv_data = request.session.get('csv_output')
    if not csv_data:
        return HttpResponse("No output to download. Upload a file first.", status=400)

    response = HttpResponse(csv_data, content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="adx_output.csv"'
    return response
