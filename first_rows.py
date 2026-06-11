import pandas as pd

df = pd.read_csv('IPL.csv')
df.head(1).to_csv('first_rows.csv', index=False)
