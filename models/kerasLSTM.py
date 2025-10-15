import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import mean_squared_error, r2_score
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout, Input
from tensorflow.keras.callbacks import EarlyStopping

# ---------------------------
# Dataset Creation
# ---------------------------
def create_dataset(dataset, look_back=60):
    X, Y = [], []
    for i in range(len(dataset) - look_back - 1):
        X.append(dataset[i:(i + look_back), :])
        Y.append(dataset[i + look_back, 0])  # predict Close (col 0)
    return np.array(X), np.array(Y)

# ---------------------------
# Model Training
# ---------------------------
def train_keras_lstm(train_data, val_data, look_back=60,
                     units=50, num_layers=2, dropout=0.2,
                     epochs=100, batch_size=32):
    num_features = train_data.shape[1]

    X_train, y_train = create_dataset(train_data, look_back)
    X_val, y_val = create_dataset(val_data, look_back)

    model = Sequential()
    model.add(Input(shape=(look_back, num_features)))
    model.add(LSTM(units=units, return_sequences=(num_layers > 1)))
    if dropout > 0:
        model.add(Dropout(dropout))

    for i in range(num_layers - 2):
        model.add(LSTM(units=units, return_sequences=True))
        if dropout > 0:
            model.add(Dropout(dropout))

    if num_layers > 1:
        model.add(LSTM(units=units, return_sequences=False))
        if dropout > 0:
            model.add(Dropout(dropout))

    model.add(Dense(1))

    model.compile(optimizer="adam", loss="mean_squared_error")

    early_stopping = EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)

    history = model.fit(
        X_train, y_train,
        epochs=epochs,
        batch_size=batch_size,
        validation_data=(X_val, y_val),
        callbacks=[early_stopping],
        verbose=1
    )

    return model, history

# ---------------------------
# Evaluation & Plot
# ---------------------------
def evaluate_and_plot(model, test_data, scaler, look_back=60, zoom_range=100):
    X_test, y_test = create_dataset(test_data, look_back)

    predicted_scaled = model.predict(X_test)

    # Ensure correct shape for inverse_transform
    predicted = scaler.inverse_transform(np.repeat(predicted_scaled, test_data.shape[1], axis=-1))[:, 0]
    actual = scaler.inverse_transform(np.repeat(y_test.reshape(-1, 1), test_data.shape[1], axis=-1))[:, 0]

    rmse = float(np.sqrt(mean_squared_error(np.array(actual).flatten(), np.array(predicted).flatten())))
    r2 = float(r2_score(np.array(actual).flatten(), np.array(predicted).flatten()))

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(np.array(actual[-zoom_range:]), label="Actual Price")
    ax.plot(np.array(predicted[-zoom_range:]), label="Predicted Price")
    ax.set_title(f"Keras LSTM Prediction (Last {zoom_range} Days)\nRMSE: {rmse:.4f}, R²: {r2:.4f}")
    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    ax.legend()

    # ---------------------------
    # Next Future Price Prediction
    # ---------------------------
    last_window = test_data[-look_back:]
    X_future = last_window.reshape(1, look_back, -1)
    predicted_next_scaled = model.predict(X_future)
    predicted_next = scaler.inverse_transform(np.repeat(predicted_next_scaled, test_data.shape[1], axis=-1))[:, 0]

    return fig, predicted, actual, {"rmse": rmse, "r2": r2, "next_price": float(predicted_next[0])}



