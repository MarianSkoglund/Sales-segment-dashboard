# Executive Revenue Analytics Dashboard

Production-ready Streamlit dashboard for executive revenue analysis across industries, countries or regions, and time periods.

The Streamlit application source lives in the `app/` folder.

## Detected Workbook Mapping

The source workbook `Adjusted gross sales combined 2024-2026Q1.xlsx` was inspected before implementation.

| Excel Column | Detected Header | Dashboard Field | Business Meaning |
| --- | --- | --- | --- |
| D | Ext. invoice | `ext_invoice` | Ext. Invoice |
| H | Industry | `industry` | Industry |
| M | BA Region (T) | `country` | Country / Region |
| T | Period | `period` | Date / Period |

The prompt's expected D and T meanings are swapped in the workbook. The application uses the actual detected mapping above and only loads these four columns.

## Local Setup

```bash
cd app
pip install -r requirements.txt
streamlit run app.py
```

## Data Placement

Place the default Excel workbook in the same folder as `app.py`:

```text
app/
|-- app.py
|-- Adjusted gross sales combined 2024-2026Q1.xlsx
`-- ...
```

The sidebar uploader can replace the default workbook during a session. Uploaded workbooks must keep the same business fields in columns D, H, M, and T.

## Deployment to Streamlit Community Cloud

1. Connect this GitHub repository in Streamlit Community Cloud.
2. Set the main file path to `app/app.py`.
3. Confirm `app/requirements.txt` is detected.
4. Decide how the Excel workbook should be supplied:
   - Commit a non-sensitive workbook with the app for a default data source.
   - Or omit the workbook and use the sidebar upload option.

## Environment Notes

- Python 3.10 or later is recommended.
- The app uses `openpyxl` for Excel loading.
- No database or external service is required.
- The dashboard uses Plotly only for visualizations.
- If the default workbook is missing, the app shows deterministic mock fallback data so the interface can still be reviewed.
