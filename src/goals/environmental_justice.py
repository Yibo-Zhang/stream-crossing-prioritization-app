"""Environmental Justice calculations."""
import pandas as pd
import numpy as np

def calculate_ej(df, params):
    df['EJ'] = df['EJScr'].map({1: 'disadvantaged'})
    return df
