# =====================
# data_loader.py
# =====================
import yfinance as yf
import pandas as pd
from sklearn.preprocessing import MinMaxScaler


def load_data(
    ticker: str,
    period: str = "max",
    interval: str = "1d",
    prepost: bool = False
) -> pd.DataFrame:
    """
    Download historical stock data using yfinance.

    Args:
        ticker (str): Stock ticker symbol.
        period (str): Period of data to download (e.g., '1y', '5d', 'max').
        interval (str): Data interval (e.g., '1m', '5m', '1d').
        prepost (bool): Whether to include pre/post-market data (only for intraday intervals).

    Returns:
        pd.DataFrame: DataFrame containing stock OHLCV data.
    """
    df = yf.download(ticker, period=period, interval=interval, prepost=prepost)
    return df


def add_rsi(df: pd.DataFrame, window: int = 14) -> pd.DataFrame:
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    df[f"RSI_{window}"] = 100 - (100 / (1 + rs))
    df.fillna(0, inplace=True)
    return df


def scale_data(df: pd.DataFrame, feature_range=(0, 1)):
    scaler_all = MinMaxScaler(feature_range=feature_range)
    scaled_values = scaler_all.fit_transform(df.values)
    scaled_df = pd.DataFrame(scaled_values, index=df.index, columns=df.columns)

    # scaler for Close only
    scaler_close = MinMaxScaler(feature_range=feature_range)
    scaler_close.fit(df[["Close"]])

    return scaled_df, scaler_all, scaler_close


def inverse_scale(scaled_data, scaler: MinMaxScaler, columns: list):
    inv_values = scaler.inverse_transform(scaled_data)
    return pd.DataFrame(inv_values, columns=columns)