import pandas as pd

def extract_excel(file):
    df = pd.read_excel(file)
    return df
