import sqlite3
import pandas as pd
from datetime import datetime, timedelta

# === 1. Conectare la baza de date SQLite ===
db_path = "forecast\generated_data.db"  # Înlocuiește cu calea ta reală
conn = sqlite3.connect(db_path)

# === 2. Extrage datele din tabel ===
query = "SELECT entry_time, exit_time FROM session"
df = pd.read_sql_query(query, conn)

# === 3. Convertim coloanele în datetime (format ISO: YYYY-MM-DDTHH:MM:SS) ===
df['entry_time'] = pd.to_datetime(df['entry_time'], format='%Y-%m-%dT%H:%M:%S')
df['exit_time'] = pd.to_datetime(df['exit_time'], format='%Y-%m-%dT%H:%M:%S')

# Eliminăm înregistrările fără date valide
df = df.dropna(subset=['entry_time', 'exit_time'])

# === 4. Determinăm intervalul de timp global ===
start_time = df['entry_time'].min().floor('H')  # prima oră întreagă
end_time = df['exit_time'].max().ceil('H')      # ultima oră întreagă

print(f"Interval de analiză: {start_time} → {end_time}")

# === 5. Generăm toate orele posibile în acest interval ===
hours_range = pd.date_range(start=start_time, end=end_time, freq='H')

# Creăm DataFrame gol pentru rezultat
result_df = pd.DataFrame({
    'date': hours_range.date,
    'hour': hours_range.hour,
    'cars_present': 0
})

# === 6. Pentru fiecare oră, numărăm mașinile prezente ===
# Mașina este prezentă la o anumită oră H dacă: entry <= H < exit
for idx, hour in enumerate(hours_range):
    mask = (df['entry_time'] <= hour) & (df['exit_time'] > hour)
    result_df.loc[idx, 'cars_present'] = mask.sum()

# === 7. Opțional: eliminăm orele fără nicio mașină (pentru curățenie) ===
# result_df = result_df[result_df['cars_present'] > 0].reset_index(drop=True)

# === 8. Salvează rezultatul în CSV ===
result_df.to_csv('forecast\cars_per_hour_per_day.csv', index=False)
print("\n✅ Rezultat salvat în 'cars_per_hour_per_day.csv'")

# === 9. (Opțional) Salvează și într-un nou tabel SQLite ===
result_df.to_sql('cars_by_hour', conn, if_exists='replace', index=False)
print("✅ Tabelul 'cars_by_hour' a fost creat în baza de date.")

# Închidem conexiunea
conn.close()