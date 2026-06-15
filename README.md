# Gen3 CDU CW — Log Dashboard

## Run locally
python -m streamlit run cdu_dashboard_st.py
Opens at http://localhost:8501

## Local folder mode
Set MASTER_ROOT at top of cdu_dashboard_st.py to your log root.
App auto-discovers all sites (Chester/Dalton/Ellendale/Round Rock) and units.

## Upload mode
Leave MASTER_ROOT = "" — upload a zip or individual files in the browser.

## Deploy to Streamlit Cloud (free)
1. Push repo to GitHub
2. Go to share.streamlit.io → New app → pick this repo
3. Main file: cdu_dashboard_st.py → Deploy
4. Share the URL with your team — no Python install needed

## Auto-redeploy
Every git push updates the live app automatically.
