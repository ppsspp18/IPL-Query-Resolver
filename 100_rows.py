import pandas as pd

df = pd.read_csv('IPL.csv')
df.head(100).to_csv('first_100_rows.csv', index=False)
