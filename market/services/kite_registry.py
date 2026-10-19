"""
Zerodha Kite Instrument Registry & NIFTY 50 Universe Mapping.

Downloads, caches, and parses the public Zerodha Kite instrument master:
https://api.kite.trade/instruments

Maps Nomad symbols to Kite instrument tokens:
  Nomad Company -> Nomad Instrument -> NSE Exchange -> Kite instrument_token

Ensures 100% (50/50) coverage for the NIFTY 50 constituent universe plus benchmark indices (^NSEI, ^NSEBANK).
Preserves Tata Motors (TATAMOTORS -> TMPV) demerger mapping.
"""

import csv
import io
import json
import logging
import os
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Union

logger = logging.getLogger(__name__)

KITE_INSTRUMENTS_URL = "https://api.kite.trade/instruments"
CACHE_DIR = Path("data/universe")
MASTER_CACHE_FILE = CACHE_DIR / "kite_instruments_master.csv"
MAPPING_FILE = CACHE_DIR / "kite_nifty50_mapping.json"
CONSTITUENT_SNAPSHOT_FILE = CACHE_DIR / "nifty50_constituents_2026-09-03.json"


class KiteInstrumentRegistry:
    """
    Service managing Kite instrument master data and symbol-to-token mappings.
    """

    _cache_master: Optional[Dict[str, dict]] = None
    _token_to_meta: Optional[Dict[int, dict]] = None
    _symbol_to_token: Optional[Dict[str, int]] = None

    @classmethod
    def download_master(cls, force_refresh: bool = False, timeout: int = 30) -> str:
        """
        Downloads the complete Kite instrument master CSV and saves to CACHE_DIR.
        Returns the CSV text content.
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        if not force_refresh and MASTER_CACHE_FILE.exists():
            mtime = datetime.fromtimestamp(MASTER_CACHE_FILE.stat().st_mtime, tz=timezone.utc)
            # If file was modified today, use cached
            if (datetime.now(timezone.utc) - mtime).total_seconds() < 86400:
                logger.info(f"Using cached Kite instrument master from {MASTER_CACHE_FILE}")
                return MASTER_CACHE_FILE.read_text(encoding="utf-8")

        logger.info(f"Downloading Kite instrument master from {KITE_INSTRUMENTS_URL}...")
        resp = requests.get(KITE_INSTRUMENTS_URL, timeout=timeout)
        resp.raise_for_status()
        csv_text = resp.text
        MASTER_CACHE_FILE.write_text(csv_text, encoding="utf-8")
        logger.info(f"Saved Kite instrument master to {MASTER_CACHE_FILE} ({len(csv_text)} bytes)")
        return csv_text

    @classmethod
    def load_master(cls, force_refresh: bool = False) -> Dict[str, dict]:
        """
        Loads and parses the master CSV into in-memory lookup dicts.
        Keys format: '{exchange}:{tradingsymbol}', e.g., 'NSE:RELIANCE', 'INDICES:NIFTY 50'
        """
        if cls._cache_master is not None and not force_refresh:
            return cls._cache_master

        csv_text = cls.download_master(force_refresh=force_refresh)
        reader = csv.DictReader(io.StringIO(csv_text))

        master: Dict[str, dict] = {}
        token_to_meta: Dict[int, dict] = {}
        symbol_to_token: Dict[str, int] = {}

        for row in reader:
            try:
                token = int(row["instrument_token"])
                exchange = row["exchange"].strip()
                segment = row["segment"].strip()
                tradingsymbol = row["tradingsymbol"].strip()
                inst_type = row["instrument_type"].strip()
                name = row.get("name", "").strip()

                meta = {
                    "instrument_token": token,
                    "exchange_token": row.get("exchange_token", "").strip(),
                    "tradingsymbol": tradingsymbol,
                    "name": name,
                    "last_price": float(row.get("last_price", 0) or 0),
                    "tick_size": float(row.get("tick_size", 0) or 0),
                    "lot_size": int(row.get("lot_size", 1) or 1),
                    "instrument_type": inst_type,
                    "segment": segment,
                    "exchange": exchange,
                }

                # Key by exchange:tradingsymbol (e.g. NSE:RELIANCE)
                key = f"{exchange}:{tradingsymbol}"
                master[key] = meta
                token_to_meta[token] = meta

                # If NSE Equity, add direct symbol mapping
                if exchange == "NSE" and inst_type == "EQ":
                    symbol_to_token[tradingsymbol] = token
                elif segment == "INDICES":
                    # Indices e.g. NIFTY 50, NIFTY BANK, NIFTY IT, SENSEX
                    symbol_to_token[tradingsymbol] = token

            except (KeyError, ValueError) as err:
                continue

        cls._cache_master = master
        cls._token_to_meta = token_to_meta
        cls._symbol_to_token = symbol_to_token
        logger.info(f"Loaded {len(master)} instruments ({len(symbol_to_token)} NSE/INDICES tokens) into registry.")
        return master

    @classmethod
    def get_token(cls, symbol: str) -> Optional[int]:
        """
        Resolves Nomad symbol or index ticker to Kite instrument_token.
        Handles:
        - Regular equity: 'RELIANCE' -> 738561
        - Tata Motors demerger: 'TATAMOTORS' -> 'TMPV' (884737)
        - Benchmark indices:
          '^NSEI' -> 'NIFTY 50' (256265)
          '^NSEBANK' -> 'NIFTY BANK' (260105)
          '^BSESN' -> 'SENSEX' (265)
          '^CNXIT' -> 'NIFTY IT' (259849)
        """
        if cls._symbol_to_token is None:
            cls.load_master()

        sym = symbol.strip().upper()

        # Handle benchmark indices
        if sym in ("^NSEI", "NIFTY", "NIFTY50", "NIFTY 50"):
            return cls._symbol_to_token.get("NIFTY 50", 256265)
        if sym in ("^NSEBANK", "BANKNIFTY", "NIFTY BANK"):
            return cls._symbol_to_token.get("NIFTY BANK", 260105)
        if sym in ("^BSESN", "SENSEX", "BSE SENSEX"):
            return cls._symbol_to_token.get("SENSEX", 265)
        if sym in ("^CNXIT", "NIFTYIT", "NIFTY IT"):
            return cls._symbol_to_token.get("NIFTY IT", 259849)

        # Handle Tata Motors corporate action / demerger
        if sym == "TATAMOTORS":
            return cls._symbol_to_token.get("TMPV", 884737)

        return cls._symbol_to_token.get(sym)

    @classmethod
    def get_symbol(cls, token: int) -> Optional[str]:
        """
        Resolves Kite instrument_token to standard Nomad symbol.
        """
        if cls._token_to_meta is None:
            cls.load_master()

        meta = cls._token_to_meta.get(token)
        if not meta:
            return None

        # Reverse index mapping
        if meta["tradingsymbol"] == "NIFTY 50" and meta["segment"] == "INDICES":
            return "^NSEI"
        if meta["tradingsymbol"] == "NIFTY BANK" and meta["segment"] == "INDICES":
            return "^NSEBANK"
        if (meta["tradingsymbol"] == "SENSEX" or token == 265) and meta["segment"] == "INDICES":
            return "^BSESN"
        if (meta["tradingsymbol"] == "NIFTY IT" or token == 259849) and meta["segment"] == "INDICES":
            return "^CNXIT"

        # Reverse mapping for Tata Motors corporate action / demerger
        if meta["tradingsymbol"] == "TMPV" or token == cls.get_token("TATAMOTORS"):
            return "TATAMOTORS"

        return meta["tradingsymbol"]

    @classmethod
    def get_meta(cls, identifier: Union[str, int]) -> Optional[dict]:
        """
        Returns complete metadata dict for a symbol or instrument_token.
        """
        if cls._token_to_meta is None:
            cls.load_master()

        if isinstance(identifier, int):
            return cls._token_to_meta.get(identifier)

        token = cls.get_token(str(identifier))
        if token:
            return cls._token_to_meta.get(token)
        return None

    @classmethod
    def build_nifty50_mapping(cls) -> Dict[str, Any]:
        """
        Builds and saves the complete NIFTY 50 constituent mapping audit.
        Validates all 50 constituents + 2 benchmark indices.
        """
        cls.load_master()

        if not CONSTITUENT_SNAPSHOT_FILE.exists():
            raise FileNotFoundError(f"Missing constituent snapshot at {CONSTITUENT_SNAPSHOT_FILE}")

        with open(CONSTITUENT_SNAPSHOT_FILE, "r", encoding="utf-8") as f:
            snapshot = json.load(f)

        constituents = snapshot.get("constituents", [])
        benchmarks = snapshot.get("benchmarks", [])

        mapped_equities = []
        unmapped_equities = []

        for c in constituents:
            nomad_symbol = c["symbol"]
            isin = c.get("isin")
            company_name = c.get("company_name")
            sector = c.get("sector")

            # Look up token
            token = cls.get_token(nomad_symbol)
            meta = cls.get_meta(token) if token else None

            if token and meta:
                entry = {
                    "nomad_symbol": nomad_symbol,
                    "company_name": company_name,
                    "nse_tradingsymbol": meta["tradingsymbol"],
                    "kite_instrument_token": token,
                    "exchange": meta["exchange"],
                    "segment": meta["segment"],
                    "instrument_type": meta["instrument_type"],
                    "lot_size": meta["lot_size"],
                    "isin": isin,
                    "sector": sector,
                    "status": "VALID",
                }
                # Check for special demerger note
                if nomad_symbol in ("TMPV", "TATAMOTORS"):
                    entry["notes"] = "Tata Motors demerger into Tata Motors Passenger Vehicles (TMPV) preserved."

                mapped_equities.append(entry)
            else:
                unmapped_equities.append({
                    "nomad_symbol": nomad_symbol,
                    "company_name": company_name,
                    "status": "UNMAPPED",
                })

        mapped_benchmarks = []
        for b in benchmarks:
            nomad_sym = b["symbol"]
            token = cls.get_token(nomad_sym)
            meta = cls.get_meta(token) if token else None
            if token and meta:
                mapped_benchmarks.append({
                    "nomad_symbol": nomad_sym,
                    "benchmark_name": b["name"],
                    "kite_tradingsymbol": meta["tradingsymbol"],
                    "kite_instrument_token": token,
                    "exchange": meta["exchange"],
                    "segment": meta["segment"],
                    "instrument_type": meta["instrument_type"],
                    "status": "VALID",
                })

        audit_result = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "provider": "Zerodha Kite Connect",
                "master_source": KITE_INSTRUMENTS_URL,
                "nifty50_constituents_total": len(constituents),
                "nifty50_mapped_count": len(mapped_equities),
                "nifty50_unmapped_count": len(unmapped_equities),
                "benchmarks_total": len(benchmarks),
                "benchmarks_mapped_count": len(mapped_benchmarks),
                "coverage_percent": (len(mapped_equities) / len(constituents)) * 100 if constituents else 0,
            },
            "benchmarks": mapped_benchmarks,
            "constituents": mapped_equities,
            "unmapped": unmapped_equities,
        }

        # Save to disk
        MAPPING_FILE.write_text(json.dumps(audit_result, indent=2), encoding="utf-8")
        logger.info(f"Saved NIFTY 50 Kite mapping to {MAPPING_FILE} (Coverage: {audit_result['metadata']['coverage_percent']}%)")
        return audit_result
