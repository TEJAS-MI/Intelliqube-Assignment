# adxapp/views.py

import pandas as pd
from django.shortcuts import render, redirect
from django.http import HttpResponse
from .utils import calculate_adx # IMPORTANT: Ensure utils.py is correct
import matplotlib.pyplot as plt
import io
import base64
import os

# CRITICAL FIX for plotting hang on Windows/headless servers
# Must be before any plt.figure() or plt.plot() calls
if os.environ.get('DISPLAY') is None:
    plt.switch_backend('Agg') 

# Temporary global storage for the result DataFrame
RESULTS_DATAFRAME = pd.DataFrame() 

def index(request):
    """Displays the initial file upload form."""
    return render(request, 'adxapp/index.html')

def process_file(request):
    """Handles file upload, runs ADX calculation, generates plot, and shows results."""
    global RESULTS_DATAFRAME
    
    if request.method == 'POST':
        if 'csv_file' not in request.FILES:
            return render(request, 'adxapp/index.html', {'error': 'No file selected.'})
            
        uploaded_file = request.FILES['csv_file']
            
        try:
            # 1. Read the uploaded CSV file, setting the first column (Date/Time) as the index
            df = pd.read_csv(uploaded_file, index_col=0)
            
            # 2. Run the ADX Calculation
            results_df = calculate_adx(df) 
            
            # 3. Store results for download
            RESULTS_DATAFRAME = results_df.copy()

            # --- 4. Generate Plot (for result.html) ---
            # Use results_df.index.tolist() to handle potential datetime index for labeling
            plot_index = results_df.index[14:].tolist() 
            
            fig, ax = plt.subplots(figsize=(12, 6))
            
            # Plot the required columns, starting from the 15th row (index 14) 
            # to skip initial NaNs/unstable values
            ax.plot(plot_index, results_df['ADX'].iloc[14:], label='ADX (14)', color='blue')
            ax.plot(plot_index, results_df['+DI14'].iloc[14:], label='+DI (14)', color='green')
            ax.plot(plot_index, results_df['-DI14'].iloc[14:], label='-DI (14)', color='red')
            
            # Format the X-axis to show only a few relevant labels
            n_ticks = 5
            tick_indices = [int(i * (len(plot_index) / n_ticks)) for i in range(n_ticks)]
            ax.set_xticks([plot_index[i] for i in tick_indices])
            ax.set_xticklabels([str(plot_index[i]) for i in tick_indices], rotation=45, ha='right')

            ax.legend(loc='upper right')
            ax.set_title('ADX and Directional Indicators (N=14)')
            ax.set_ylabel('Value')
            ax.grid(True, alpha=0.5)
            
            # Save plot to an in-memory buffer
            buffer = io.BytesIO()
            plt.savefig(buffer, format='png', bbox_inches='tight')
            plt.close(fig) 
            
            # Encode the image to base64
            plot_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # --- 5. Prepare data for preview table ---
            preview_df = results_df.head(10).reset_index() 
            # Format the index/date column for display
            preview_df.iloc[:, 0] = preview_df.iloc[:, 0].astype(str) 
            
            context = {
                'plot_base64': plot_base64,
                'preview_columns': preview_df.columns.tolist(),
                'preview_data': preview_df.values.tolist(), 
                'success': True,
            }
            return render(request, 'adxapp/result.html', context)
            
        except Exception as e:
            # If an error happens, we redirect to the index page with the error shown
            error_message = f"Error processing file: {e}. Check utils.py logic or file format."
            return render(request, 'adxapp/index.html', {'error': error_message})
    
    return redirect('index')

def download_csv(request):
    """Handles the 'Download Output' button click."""
    global RESULTS_DATAFRAME

    if RESULTS_DATAFRAME.empty:
        return HttpResponse("No data to download. Please upload and process a file first.", status=400)
    
    # Configure the HTTP response for CSV download
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="adx_solution.csv"'

    # Write the DataFrame to the response, including the index (Date/Time)
    RESULTS_DATAFRAME.to_csv(response, index=True)
    return response