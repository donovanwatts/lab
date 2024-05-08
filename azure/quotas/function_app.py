import azure.functions as func
import logging
import pandas as pd
import gspread
from gspread.utils import rowcol_to_a1
from gspread_formatting import *
from google.oauth2.service_account import Credentials
import json
import utils
import os
from credentials import secret

scopes = ["https://www.googleapis.com/auth/spreadsheets"]

def get_google_credentials_from_key_vault():
    # Convert the secret value to a dictionary
    service_account_info = json.loads(secret.value)
    credentials = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    return credentials

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

@app.route(route="main")
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        # Parse the request body
        req_body = req.get_json()
        sheet_url = req_body.get('sheet_url')
        worksheet_name = req_body.get('worksheet_name')
        
        
        # Get Google Sheets credentials from Azure Key Vault
        credentials = get_google_credentials_from_key_vault()
    
        # Authenticate with Google Sheets API
        gc = gspread.authorize(credentials)

        # Extract Sheet ID from URL and access the worksheet
        sheet_id = sheet_url.split("/d/")[1].split("/")[0]
        spreadsheet = gc.open_by_key(sheet_id)
        worksheet = spreadsheet.worksheet(worksheet_name)
        
        # Read data into DataFrame
        values = worksheet.get_all_values()

        # Define headers located on Row 2
        headers = values[1]

        # Find the row where 'DATA BEGINS HERE - QUOTA' is located
        data_start_row = next(i for i, row in enumerate(values) if
                            row[0] == 'DATA BEGINS HERE - QUOTA') + 1

        # Adjust for data starting below 'DATA BEGINS HERE - QUOTA'
        data_values = values[data_start_row:]

        # Create DataFrame with proper headers
        df = pd.DataFrame(data_values, columns=headers)

        # Adjust for checkboxes in Row 1 to filter columns
        include_columns = [val.lower() == 'true' for val in values[0]]
        filtered_df = df.loc[:, include_columns]

        # Attempt to create a new sheet or clear it if it already exists
        try:
            results_sheet = spreadsheet.add_worksheet(title="Quotas for Client",
                                                    rows="1000", cols="26")
        except gspread.exceptions.APIError:
            results_sheet = spreadsheet.worksheet('Quotas for Client')
            results_sheet.clear()

        start_col_idx = 1

        # Assuming 'include_columns' is a list of booleans indicating whether each column is included based on Row 1 checkboxes
        # and 'df' is the initial DataFrame before filtering
        critical_columns = df.columns[include_columns]

        # Replace empty strings with NaN to prepare for dropping rows
        filtered_df = filtered_df.replace('', pd.NA)

        # Drop rows where all critical columns are NaN
        filtered_df = filtered_df.dropna(subset=critical_columns, how='all').reset_index(drop=True)

        for column in filtered_df.columns:
            # Generate value counts
            counts = filtered_df[column].value_counts().reset_index()
            counts.columns = [column, 'Counts']

            # Define the cell range for the update
            start_cell = rowcol_to_a1(1, start_col_idx)
            end_cell = rowcol_to_a1(len(counts) + 1, start_col_idx + 1)

            # Prepare data including headers
            data = [counts.columns.tolist()] + counts.values.tolist()

            # Correctly update the sheet using the 'range_name' parameter
            results_sheet.update(range_name=f'{start_cell}:{end_cell}', values=data)

            # Apply formatting to the header
            rgb_color = utils.hex_to_normalized_rgb("#27688b")
            header_format = cellFormat(
                backgroundColor=Color(rgb_color[0], rgb_color[1], rgb_color[2]),
                textFormat=textFormat(bold=True, foregroundColor=Color(1, 1, 1)),
                horizontalAlignment='CENTER'
            )

            header_range = f'{utils.get_col_letter(start_col_idx)}1:{utils.get_col_letter(start_col_idx + 1)}1'
            format_cell_range(results_sheet, header_range, header_format)

            start_col_idx += 2
        
        return func.HttpResponse(
            "Data processed successfully.",
            status_code=200
        )
    except Exception as e:
        return func.HttpResponse(
            f"Error processing request: {str(e)}",
            status_code=400
        )