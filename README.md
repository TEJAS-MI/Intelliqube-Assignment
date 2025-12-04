 # ADX Calculator – Intelliqube Assignment

A Django-based web application that calculates Average Directional Index (ADX) along with +DI, -DI, TR, DM, DX, and smoothed Wilder 14-period values, replicating Excel’s logic exactly.

This project was submitted as part of the Intelliqube Capital technical assignment.

# Features

Upload OHLC (Open, High, Low, Close) CSV file

Automatic detection of OHLC columns

TR, +DM, -DM calculations

Wilder’s smoothing logic to compute TR14, DM14

DI14, DX, and final ADX computation

Automatically generates:

Graph of ADX, +DI14, -DI14

Processed CSV file

Preview of first 10 rows

Formatted Excel-like output

Compatible with Python 3.6 (as required)

# ADX Formula Summary (as implemented)

This project follows the exact formulas from the assignment:

True Range (TR)
TR = max( High - Low, |High - PrevClose|, |Low - PrevClose| )

Directional Movement
+DM = High - PrevHigh (only if UpMove > DownMove and > 0)
-DM = PrevLow - Low   (only if DownMove > UpMove and > 0)

Wilder's Smoothing (TR14, +DM14, -DM14)

Row 15 (index 14):

Sum of rows 2–15 (14 values)


Row 16 onward:

Smoothed = PreviousSum – (PreviousSum / 14) + CurrentValue

Directional Indicators
+DI14 = (+DM14 / TR14) * 100
-DI14 = (-DM14 / TR14) * 100

DX
DX = |(+DI14 – -DI14)| / (+DI14 + -DI14) * 100

ADX

Row 29 (index 28):

Average of 14 DX values


Row 30 onward:

ADX = (PreviousADX * 13 + CurrentDX) / 14

# Project Structure
<img width="265" height="432" alt="project Structure" src="https://github.com/user-attachments/assets/8215e7d5-8509-4de0-87cc-87a5dcd0092f" />


# Technologies Used

Python 3.6

Django

Pandas

NumPy

Matplotlib

HTML / Bootstrap

# Installation & Setup
1. Clone the repository
git clone https://github.com/TEJAS-MI/Intelliqube-Assignment.git
cd Intelliqube-Assignment

2. Create a Virtual Environment (Python 3.6)
python -m venv venv

3. Activate the Environment
Windows:
venv\Scripts\activate

4. Install Requirements
pip install -r requirements.txt

5. Run the Django Server
python manage.py runserver

6. Open in Browser
http://127.0.0.1:8000/

# How to Use

Go to the homepage

Upload an OHLC CSV file

Click "Upload & Calculate ADX"

View:

ADX graph

Table preview

Downloadable CSV

# Sample Output

The application generates:

✔ ADX Plot
✔ Smoothed values (TR14, +DM14, -DM14)
✔ DI14 and DX
✔ Final ADX column matching Excel output

# output (Result) Graph
<img width="1295" height="680" alt="Assignment output graph" src="https://github.com/user-attachments/assets/4183b4f9-4a05-461c-bbc0-602912745709" />


# Final output what i am getting
[adx_output.csv](https://github.com/user-attachments/files/23927896/adx_output.csv)

