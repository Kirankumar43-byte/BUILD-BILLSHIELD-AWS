# 2-minute demo script
0:00 Welcome screen: "Students get surprise AWS bills. BillShield finds the waste and risks first." Click **Try Demo Mode**.
0:20 Overview: KPI cards, Bill Shock Meter, health score. Click a question in **Ask BillShield**.
0:50 Switch language to தமிழ் then മലയാളം: everything changes, commands stay in English.
1:05 Findings: filter Critical, open the SSH finding, show Facts vs Explanation vs dry-run command.
1:30 Forecast: dashed forecast, budget line, the spike flagged by the anomaly alert.
1:45 Fix Guide: tick findings in the **Savings Simulator** (score rises), show the typed-confirmation safety. Audit Log.

# LinkedIn post (edit with your own numbers)
I built BillShield: a read-only AWS cost + security guardian for students, with a Streamlit dashboard in English, Tamil, Hindi and Malayalam. It scans for idle resources and risky settings, forecasts the month-end bill, scores account health and only fixes things after typed confirmation. Built with Python, boto3, moto tests, SQLite and Plotly. Demo Mode needs no AWS account. #AWS #Python #CloudSecurity #FinOps

# Resume bullets (replace brackets with YOUR measured results)
- Built a read-only AWS scanner (boto3) detecting 5 waste types and 3 security risks; validated with 20 automated tests (pytest + moto).
- Designed a capped 0-100 health score and month-end forecast with anomaly detection; found [X] USD/month of estimated waste in [my test account].
- Shipped a 4-language (EN/TA/HI/ML) Streamlit dashboard with dry-run-by-default actions, typed confirmation and an SQLite audit log.
