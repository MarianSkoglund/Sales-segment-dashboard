# Executive Revenue Analytics Dashboard

Production-ready Streamlit dashboard for executive revenue analysis across industries, countries or regions, and time periods.

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
pip install -r requirements.txt
streamlit run app.py
```

Run the commands from this `app` folder.

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

1. Push this `app` folder to a GitHub repository.
2. In Streamlit Community Cloud, create a new app from the repository.
3. Set the main file path to:

```text
app.py
```

If the repository root contains this folder rather than the app files directly, set the main file path to:

```text
app/app.py
```

4. Confirm `requirements.txt` is included.
5. Decide how the Excel workbook should be supplied:
   - Commit a non-sensitive workbook with the app for a default data source.
   - Or omit the workbook and use the sidebar upload option.

## Environment Notes

- Python 3.10 or later is recommended.
- The app uses `openpyxl` for Excel loading.
- No database or external service is required.
- The dashboard uses Plotly only for visualizations.
- If the default workbook is missing, the app shows deterministic mock fallback data so the interface can still be reviewed.
