import os
from datetime import datetime
import pandas as pd
import pyotp
import streamlit as st

class AngelData:
    def __init__(self):
        try:
            secrets = st.secrets.get("angel", {})
        except Exception:
            secrets = {}
        self.api_key = secrets.get("api_key") or os.getenv("ANGEL_API_KEY")
        self.client_code = secrets.get("client_code") or os.getenv("ANGEL_CLIENT_CODE")
        self.pin = secrets.get("pin") or os.getenv("ANGEL_PIN")
        self.totp_secret = secrets.get("totp_secret") or os.getenv("ANGEL_TOTP_SECRET")
        self.smart = None
        self.ready = False

    @property
    def credentials_present(self):
        return all([self.api_key, self.client_code, self.pin, self.totp_secret])

    def login(self):
        if not self.credentials_present:
            raise RuntimeError("Missing Angel credentials. Configure Streamlit secrets.")
        try:
            from SmartApi import SmartConnect
        except ImportError as exc:
            raise RuntimeError("Install smartapi-python dependency.") from exc
        self.smart = SmartConnect(api_key=self.api_key)
        totp = pyotp.TOTP(self.totp_secret).now()
        response = self.smart.generateSession(self.client_code, self.pin, totp)
        if not response or not response.get("status"):
            raise RuntimeError(f"Angel login failed: {response}")
        self.ready = True
        return response

    def candles(self, symbol, token, interval, start, end):
        if not self.ready or self.smart is None:
            self.login()
        params = {
            "exchange": "MCX",
            "symboltoken": str(token),
            "interval": interval,
            "fromdate": start.strftime("%Y-%m-%d %H:%M"),
            "todate": end.strftime("%Y-%m-%d %H:%M"),
        }
        response = self.smart.getCandleData(params)
        if not response or not response.get("status"):
            raise RuntimeError(f"Angel historical data error for {symbol}: {response}")
        rows = response.get("data") or []
        if not rows:
            raise RuntimeError(f"No historical candles returned for {symbol}.")
        df = pd.DataFrame(rows, columns=["datetime","open","high","low","close","volume"])
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True).dt.tz_convert("Asia/Kolkata")
        for col in ["open","high","low","close","volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        return df.dropna().set_index("datetime").sort_index()
