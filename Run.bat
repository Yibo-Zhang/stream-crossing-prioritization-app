@echo off
cd /d "C:\Users\ka1210\OneDrive - USNH\Desktop\Koorosh PhD research\NFWF\Code\Version 1.8\stream-crossing-prioritization-MeanSub"

call venv\Scripts\activate

python src\model.py --input data\input\crossings.csv --skip-validation
python scripts\generate_excel_report.py

pause