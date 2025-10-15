import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import numpy as np
import matplotlib.pyplot as plt

# Device check (MPS → CUDA → CPU)
if torch.backends.mps.is_available():
    device = torch.device("mps")
elif torch.cuda.is_available():
    device = torch.device("cuda")
else:
    device = torch.device("cpu")


class GRUDataset(Dataset):
    def __init__(self, data, look_back=60):
        self.X, self.y = self.create_dataset(data, look_back)

    def create_dataset(self, dataset, look_back):
        X, Y = [], []
        for i in range(len(dataset) - look_back - 1):
            X.append(dataset[i:(i + look_back), :])
            Y.append(dataset[i + look_back, 0])  # predict 'Close' only
        return np.array(X), np.array(Y)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return (
            torch.tensor(self.X[idx], dtype=torch.float32),
            torch.tensor(self.y[idx], dtype=torch.float32),
        )


class GRUModel(nn.Module):
    def __init__(self, input_size, hidden_size=64, num_layers=2, dropout=0.3, output_size=1):
        super(GRUModel, self).__init__()
        self.gru = nn.GRU(input_size=input_size,
                          hidden_size=hidden_size,
                          num_layers=num_layers,
                          batch_first=True,
                          dropout=dropout,
                          bidirectional=True)

        self.fc1 = nn.Linear(hidden_size * 2, 128)
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)
        self.fc2 = nn.Linear(128, 64)
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)
        self.fc3 = nn.Linear(64, output_size)

    def forward(self, x):
        out, _ = self.gru(x)
        out = out[:, -1, :]
        out = self.fc1(out)
        out = self.relu1(out)
        out = self.dropout1(out)
        out = self.fc2(out)
        out = self.relu2(out)
        out = self.dropout2(out)
        out = self.fc3(out)
        return out


def train_gru(train_data, val_data, look_back=60,
              hidden_size=64, num_layers=2, dropout=0.3,
              epochs=100, batch_size=32, lr=0.001):
    train_dataset = GRUDataset(train_data, look_back)
    val_dataset = GRUDataset(val_data, look_back)

    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)

    model = GRUModel(input_size=train_data.shape[1], hidden_size=hidden_size,
                     num_layers=num_layers, dropout=dropout).to(device)
    criterion = nn.MSELoss()
    optimizer = optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.5, patience=5)

    best_val_loss = float("inf")
    patience, patience_counter = 15, 0

    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for X_batch, y_batch in train_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            optimizer.zero_grad()
            outputs = model(X_batch)
            loss = criterion(outputs.squeeze(), y_batch)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            train_loss += loss.item() * X_batch.size(0)

        train_loss /= len(train_loader.dataset)

        model.eval()
        val_loss = 0.0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch, y_batch = X_batch.to(device), y_batch.to(device)
                outputs = model(X_batch)
                loss = criterion(outputs.squeeze(), y_batch)
                val_loss += loss.item() * X_batch.size(0)

        val_loss /= len(val_loader.dataset)
        scheduler.step(val_loss)

        print(f"Epoch {epoch+1}/{epochs}, Train Loss: {train_loss:.6f}, Val Loss: {val_loss:.6f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict()
            patience_counter = 0
        else:
            patience_counter += 1
            if patience_counter >= patience:
                print("Early stopping triggered.")
                break

    model.load_state_dict(best_model_state)
    return model


def evaluate_and_plot(model, test_data, scaler_close, look_back=60, zoom_range=100):
    test_dataset = GRUDataset(test_data, look_back)
    test_loader = DataLoader(test_dataset, batch_size=1, shuffle=False)

    model.eval()
    predictions, actuals = [], []
    with torch.no_grad():
        for X_batch, y_batch in test_loader:
            X_batch, y_batch = X_batch.to(device), y_batch.to(device)
            outputs = model(X_batch)
            predictions.append(outputs.item())
            actuals.append(y_batch.item())

    predicted_scaled = np.array(predictions).reshape(-1, 1)
    actual_scaled = np.array(actuals).reshape(-1, 1)

    predicted_price = scaler_close.inverse_transform(predicted_scaled)
    actual_price = scaler_close.inverse_transform(actual_scaled)

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(actual_price[-zoom_range:], label='Actual Price (Last {} Days)'.format(zoom_range))
    ax.plot(predicted_price[-zoom_range:], label='Predicted Price (Last {} Days)')
    ax.set_title('GRU Price Prediction (Last {} Days)'.format(zoom_range))
    ax.set_xlabel('Time (Days relative to zoomed range)')
    ax.set_ylabel('Price (Original Scale)')
    ax.legend()

    return fig, predicted_price, actual_price, device