from pathlib import Path
import pandas as pd

PATH = Path("contract_master.csv")
COLUMNS = ["commodity","tradingsymbol","symboltoken","expiry","lotsize","ticksize"]

def save_contract_template():
    sample = pd.DataFrame(columns=COLUMNS)
    return sample.to_csv(index=False).encode("utf-8")

def load_contracts():
    if not PATH.exists():
        return []
    try:
        df = pd.read_csv(PATH, dtype={"symboltoken":str})
        for col in COLUMNS:
            if col not in df.columns:
                return []
        return df.fillna("").to_dict("records")
    except Exception:
        return []
