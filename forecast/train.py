import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error

# Load dataset
df = pd.read_csv("forecast\cars_per_hour_per_day.csv", parse_dates=["date"])
print(df)

# Feature engineering
df["day_of_week"] = df["date"].dt.dayofweek  # Monday=0
df["is_weekend"] = df["day_of_week"] >= 5

X = df[["hour", "day_of_week", "is_weekend"]]
y = df["cars_present"]

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

# Train model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Predict
y_pred = model.predict(X_test)

print("MAE:", mean_absolute_error(y_test, y_pred))
