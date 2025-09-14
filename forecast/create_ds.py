import sqlite3

# Conectare la baza de date
conn = sqlite3.connect('forecast/generated_data.db')
cursor = conn.cursor()

# Datele pe care le cauti
data_cautata = '2025-09-09'
ora_cautata = '22'  # fără zero la stânga, dar poate fi și '08', '15' etc.

# Query SQL
query = """
SELECT *
FROM session
WHERE SUBSTR(data_column, 1, 10) = ?
  AND SUBSTR(data_column, 12, 2) = ?
"""

# Executăm query-ul cu parametri (sigur, evităm SQL injection)
cursor.execute(query, (data_cautata, ora_cautata))

# Obținem rezultatele
rezultate = cursor.fetchall()

# Afișăm
for row in rezultate:
    print(row)

# Închidem conexiunea
conn.close()