"""
Nomad Analyst — F&O Historical Parquet & DuckDB Reader Service.

Provides high-performance, read-only analytics over authentic historical 1-minute
index and option OHLCV Parquet datasets without loading bulk data into PostgreSQL.

Important Data Constraints:
- Historical bid/ask Level-1 quotes are UNAVAILABLE in the source dataset.
  They must NEVER be fabricated or hallucinated.
- Timestamps in parquet are stored in IST (Asia/Kolkata, +05:30).
  Both IST and UTC datetime accessors are provided.
"""

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import zoneinfo

import duckdb
import pyarrow as pa

IST = zoneinfo.ZoneInfo("Asia/Kolkata")
UTC = zoneinfo.ZoneInfo("UTC")

DEFAULT_HISTORICAL_DIR = Path("data/historical/fno/nifty")


class HistoricalDataUnavailableError(Exception):
    """Raised when requested historical files or dates are not present in local storage."""
    pass


class HistoricalDataConflictError(Exception):
    """Raised when conflicting OHLCV records exist for the same contract minute."""
    pass


class HistoricalParquetReader:
    """
    Read-only DuckDB-powered reader for NIFTY spot and option historical 1-minute Parquet files.
    """

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        self.base_dir = Path(base_dir or DEFAULT_HISTORICAL_DIR)
        self.index_dir = self.base_dir / "index"
        self.options_dir = self.base_dir / "options"
        self.manifest_path = self.base_dir / "manifest.json"

    def has_index_data(self) -> bool:
        """Returns True if index/NIFTY.parquet exists."""
        return (self.index_dir / "NIFTY.parquet").exists()

    def get_available_expiries(self) -> List[str]:
        """Returns list of expiry date strings (YYYY-MM-DD) available in options/."""
        if not self.options_dir.exists():
            return []
        parquet_files = sorted(self.options_dir.glob("*.parquet"))
        return [f.stem for f in parquet_files if not f.stem.startswith(".")]

    def get_index_parquet_path(self) -> Path:
        p = self.index_dir / "NIFTY.parquet"
        if not p.exists():
            raise HistoricalDataUnavailableError(f"Index parquet not found at {p}")
        return p

    def get_option_parquet_paths(self, expiry: Optional[str] = None) -> List[Path]:
        if not self.options_dir.exists():
            return []
        if expiry:
            p = self.options_dir / f"{expiry}.parquet"
            return [p] if p.exists() else []
        return sorted([p for p in self.options_dir.glob("*.parquet") if not p.name.startswith(".")])

    def query_index_bars(
        self,
        start_dt: Union[datetime, date, str],
        end_dt: Union[datetime, date, str],
    ) -> List[Dict[str, Any]]:
        """
        Queries 1-minute NIFTY index bars between start_dt and end_dt (inclusive).
        Returns a list of dicts with:
        - timestamp_ist (datetime with Asia/Kolkata tz)
        - timestamp_utc (datetime with UTC tz)
        - open, high, low, close (Decimal)
        - volume (int)
        - trading_day (str YYYY-MM-DD)
        """
        index_file = self.get_index_parquet_path()
        start_str, end_str = self._normalize_datetime_bounds(start_dt, end_dt)

        con = duckdb.connect(database=":memory:", read_only=False)
        con.execute("SET TimeZone = 'Asia/Kolkata'")
        try:
            query = """
                SELECT 
                    timestamp,
                    open,
                    high,
                    low,
                    close,
                    volume,
                    trading_day,
                    symbol
                FROM read_parquet(?)
                WHERE timestamp::TIMESTAMPTZ >= ?::TIMESTAMPTZ 
                  AND timestamp::TIMESTAMPTZ <= ?::TIMESTAMPTZ
                ORDER BY timestamp ASC
            """
            df = con.sql(query, params=[str(index_file), start_str, end_str]).to_arrow_table()
            
            bars: List[Dict[str, Any]] = []
            for row in df.to_pylist():
                ts = row["timestamp"]
                if ts.tzinfo is None:
                    ts_ist = ts.replace(tzinfo=IST)
                else:
                    ts_ist = ts.astimezone(IST)
                ts_utc = ts_ist.astimezone(UTC)

                bars.append({
                    "timestamp_ist": ts_ist,
                    "timestamp_utc": ts_utc,
                    "open": Decimal(str(row["open"])),
                    "high": Decimal(str(row["high"])),
                    "low": Decimal(str(row["low"])),
                    "close": Decimal(str(row["close"])),
                    "volume": int(row["volume"]),
                    "trading_day": str(row["trading_day"]),
                    "symbol": str(row["symbol"]),
                })
            return bars
        finally:
            con.close()

    def query_option_bars(
        self,
        start_dt: Union[datetime, date, str],
        end_dt: Union[datetime, date, str],
        strike: Optional[Union[int, float, Decimal]] = None,
        option_type: Optional[str] = None,
        expiry: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Queries 1-minute NIFTY option bars.
        Supports predicate pushdown on strike, option_type, and expiry.
        """
        files = self.get_option_parquet_paths(expiry=expiry)
        if not files:
            return []

        start_str, end_str = self._normalize_datetime_bounds(start_dt, end_dt)
        con = duckdb.connect(database=":memory:", read_only=False)
        con.execute("SET TimeZone = 'Asia/Kolkata'")
        try:
            file_paths = [str(f) for f in files]
            params: List[Any] = [file_paths, start_str, end_str]
            where_clauses = [
                "timestamp::TIMESTAMPTZ >= ?::TIMESTAMPTZ",
                "timestamp::TIMESTAMPTZ <= ?::TIMESTAMPTZ",
            ]

            if strike is not None:
                where_clauses.append("strike = ?")
                params.append(int(strike))

            if option_type is not None:
                where_clauses.append("upper(option_type) = ?")
                params.append(option_type.upper())

            if expiry is not None:
                where_clauses.append("expiry = ?")
                params.append(str(expiry))

            where_str = " AND ".join(where_clauses)
            query = f"""
                WITH deduplicated AS (
                    SELECT DISTINCT
                        timestamp,
                        open,
                        high,
                        low,
                        close,
                        volume,
                        open_interest,
                        trading_day,
                        symbol,
                        strike,
                        option_type,
                        expiry
                    FROM read_parquet(?)
                    WHERE {where_str}
                ),
                checked AS (
                    SELECT *,
                        COUNT(*) OVER (PARTITION BY timestamp, symbol, strike, option_type, expiry) AS record_conflict_cnt
                    FROM deduplicated
                )
                SELECT * FROM checked
                ORDER BY timestamp ASC, strike ASC, option_type ASC
            """

            df = con.sql(query, params=params).to_arrow_table()
            bars: List[Dict[str, Any]] = []
            for row in df.to_pylist():
                if row.get("record_conflict_cnt", 1) > 1:
                    raise HistoricalDataConflictError(
                        f"Conflicting OHLCV data for {row['symbol']} {row['expiry']} "
                        f"{row['strike']}{row['option_type']} at {row['timestamp']}"
                    )

                ts = row["timestamp"]
                if ts.tzinfo is None:
                    ts_ist = ts.replace(tzinfo=IST)
                else:
                    ts_ist = ts.astimezone(IST)
                ts_utc = ts_ist.astimezone(UTC)

                bars.append({
                    "timestamp_ist": ts_ist,
                    "timestamp_utc": ts_utc,
                    "open": Decimal(str(row["open"])),
                    "high": Decimal(str(row["high"])),
                    "low": Decimal(str(row["low"])),
                    "close": Decimal(str(row["close"])),
                    "volume": int(row["volume"]),
                    "open_interest": int(row["open_interest"]),
                    "trading_day": str(row["trading_day"]),
                    "symbol": str(row["symbol"]),
                    "strike": int(row["strike"]),
                    "option_type": str(row["option_type"]).upper(),
                    "expiry": str(row["expiry"]),
                    "tradingsymbol": f"{row['symbol']}_{row['expiry']}_{row['strike']}_{row['option_type']}",
                    "bid_ask_available": False,  # Explicit: order book quotes do not exist in dataset
                })
            return bars
        finally:
            con.close()

    def get_trading_days(self, start_date: Optional[date] = None, end_date: Optional[date] = None) -> List[date]:
        """Returns sorted distinct trading days present in the index dataset."""
        if not self.has_index_data():
            return []

        con = duckdb.connect(database=":memory:", read_only=False)
        con.execute("SET TimeZone = 'Asia/Kolkata'")
        try:
            index_file = self.get_index_parquet_path()
            query = "SELECT DISTINCT trading_day FROM read_parquet(?) ORDER BY trading_day ASC"
            rows = con.execute(query, [str(index_file)]).fetchall()
            all_days = [date.fromisoformat(r[0]) for r in rows if r[0]]
            if start_date:
                all_days = [d for d in all_days if d >= start_date]
            if end_date:
                all_days = [d for d in all_days if d <= end_date]
            return sorted(all_days)
        finally:
            con.close()

    @staticmethod
    def _normalize_datetime_bounds(
        start: Union[datetime, date, str],
        end: Union[datetime, date, str],
    ) -> Tuple[str, str]:
        """Normalizes start and end to ISO-8601 strings with timezone for DuckDB querying."""
        def to_iso(val: Union[datetime, date, str], is_end: bool) -> str:
            if isinstance(val, str):
                s = val.strip()
                if len(s) == 10 and s.count("-") == 2:
                    val = date.fromisoformat(s)
                else:
                    val = datetime.fromisoformat(s)

            if isinstance(val, date) and not isinstance(val, datetime):
                target_time = time(23, 59, 59) if is_end else time(0, 0, 0)
                val = datetime.combine(val, target_time, tzinfo=IST)

            if isinstance(val, datetime):
                if val.tzinfo is None:
                    val = val.replace(tzinfo=IST)
                return val.astimezone(IST).isoformat()

            raise ValueError(f"Unsupported datetime value: {val}")

        return to_iso(start, False), to_iso(end, True)
