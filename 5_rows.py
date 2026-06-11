import pandas as pd

df = pd.read_csv('IPL.csv')
df.head(5).to_csv('first_5_rows.csv', index=False)
