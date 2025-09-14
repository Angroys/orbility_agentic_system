import sqlite3
import pandas as pd

db_path = "forecast\generated_data.db" 
conn = sqlite3.connect(db_path)

query = "SELECT entry_time, exit_time FROM session"
df = pd.read_sql_query(query, conn)

df['entry_time'] = pd.to_datetime(df['entry_time'], format='%Y-%m-%dT%H:%M:%S')
df['exit_time'] = pd.to_datetime(df['exit_time'], format='%Y-%m-%dT%H:%M:%S')

df = df.dropna(subset=['entry_time', 'exit_time'])
df = df.dropna(subset=['entry_time'])
df = df.dropna(subset=['exit_time'])

start_time = df['entry_time'].min().floor('H')  
end_time = df['exit_time'].max().ceil('H')     

print(f"Interval de analiză: {start_time} → {end_time}")

hours_range = pd.date_range(start=start_time, end=end_time, freq='H')

result_df = pd.DataFrame({
    'date': hours_range.date,
    'hour': hours_range.hour,
    'cars_present': 0
})


for idx, hour in enumerate(hours_range):
    mask = (df['entry_time'] <= hour) & (df['exit_time'] > hour)
    result_df.loc[idx, 'cars_present'] = mask.sum()

result_df = result_df[result_df['cars_present'] > 0].reset_index(drop=True)

result_df.to_csv('forecast\cars_per_hour_per_day.csv', index=False)

result_df.to_sql('cars_by_hour', conn, if_exists='replace', index=False)

conn.close()