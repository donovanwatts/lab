import gspread
from gspread.utils import rowcol_to_a1
import numpy as np


# Convert hexadecimal to normalized RGB values
def hex_to_normalized_rgb(hex_code):
    r = int(hex_code[1:3], 16) / 255.0
    g = int(hex_code[3:5], 16) / 255.0
    b = int(hex_code[5:7], 16) / 255.0
    return r, g, b


# Function to convert column index to Google Sheets column letter
def get_col_letter(col_idx):
    return gspread.utils.rowcol_to_a1(1, col_idx).rstrip('1')
