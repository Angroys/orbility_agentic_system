import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor

df = pd.read_csv("forecast/cars_per_hour_per_day.csv", parse_dates=["date"])
print("Dataset head:\n", df.head())

df["day_of_week"] = df["date"].dt.dayofweek
df["is_weekend"] = df["day_of_week"] >= 5
df["day_of_year"] = df["date"].dt.dayofyear 

df["day_of_year_sin"] = np.sin(2 * np.pi * df["day_of_year"] / 365)
df["day_of_year_cos"] = np.cos(2 * np.pi * df["day_of_year"] / 365)

X = df[["hour", "day_of_week", "is_weekend", "day_of_year_sin", "day_of_year_cos"]]
y = df["cars_present"]

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
print("Y_TRAIN", y_train)

model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)

results = df.loc[X_test.index, ["hour", "day_of_week", "is_weekend", "day_of_year"]].copy()
results["Actual"] = y_test.values
results["Predicted"] = y_pred
results.to_csv("forecast/results_with_day_of_year.csv", index=False)




