import pandas as pd
import glob
import os

files = glob.glob(r'd:\portfolio\*.xlsx')

for f in files:
    try:
        df = pd.read_excel(f, nrows=5)
        print(f'\n--- {os.path.basename(f)} ---')
        print('Columns:', df.columns.tolist())
        print(df.head(2))
    except Exception as e:
        print(f'Error reading {f}: {e}')
