"""
Nomad Analyst — Management Command: fetch_fno_historical

Selectively downloads authentic 1-minute NIFTY spot and option Parquet files from:
https://huggingface.co/datasets/thetrademarkk/india-index-options-1m

Safety & Operational Integrity:
- License: Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0).
- Downloads are stored under Git-ignored data/historical/fno/nifty/.
- Atomic writes via temporary files (*.tmp) followed by atomic rename.
- SHA-256 checksums and file size tracking in manifest.json.
- Exponential backoff retries for resilient downloads over flaky connections.
- Idempotent: Skips files already downloaded with matching size and checksum.
"""

from datetime import date, datetime, timedelta
import hashlib
import json
import logging
from pathlib import Path
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request
import zoneinfo

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)
IST = zoneinfo.ZoneInfo("Asia/Kolkata")

HF_REPO_ID = "thetrademarkk/india-index-options-1m"
HF_API_URL = f"https://huggingface.co/api/datasets/{HF_REPO_ID}"
HF_RAW_BASE = f"https://huggingface.co/datasets/{HF_REPO_ID}/resolve/main"

DEFAULT_OUTPUT_DIR = Path("data/historical/fno/nifty")
LICENSE_NAME = "CC BY-NC 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc/4.0/"


class Command(BaseCommand):
    help = "Selectively downloads authentic NIFTY 1-minute historical Parquet data."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start-date",
            type=str,
            default=None,
            help="Start date (YYYY-MM-DD) for historical window filtering.",
        )
        parser.add_argument(
            "--end-date",
            type=str,
            default=None,
            help="End date (YYYY-MM-DD) for historical window filtering.",
        )
        parser.add_argument(
            "--expiry",
            type=str,
            default=None,
            help="Download a specific option expiry (YYYY-MM-DD), e.g. 2026-07-07.",
        )
        parser.add_argument(
            "--symbol",
            type=str,
            default="NIFTY",
            choices=["NIFTY"],
            help="Underlying symbol (currently NIFTY).",
        )
        parser.add_argument(
            "--output-dir",
            type=str,
            default=str(DEFAULT_OUTPUT_DIR),
            help=f"Target directory (default: {DEFAULT_OUTPUT_DIR}).",
        )
        parser.add_argument(
            "--skip-index",
            action="store_true",
            help="Skip downloading the index/spot Parquet file.",
        )
        parser.add_argument(
            "--options-only",
            action="store_true",
            help="Download only option expiry files, skipping spot index.",
        )
        parser.add_argument(
            "--index-only",
            action="store_true",
            help="Download only the spot index Parquet file, skipping options.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-download even if local file exists and matches manifest.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Display files that would be downloaded without writing to disk.",
        )
        parser.add_argument(
            "--max-retries",
            type=int,
            default=5,
            help="Maximum download retry attempts per file (default: 5).",
        )

    def handle(self, *args, **options):
        symbol = options["symbol"]
        output_dir = Path(options["output_dir"])
        start_date_str = options.get("start_date")
        end_date_str = options.get("end_date")
        single_expiry = options.get("expiry")
        skip_index = options.get("skip_index") or options.get("options_only")
        index_only = options.get("index_only")
        force = options.get("force", False)
        dry_run = options.get("dry_run", False)
        max_retries = options.get("max_retries", 5)

        start_date = date.fromisoformat(start_date_str) if start_date_str else None
        end_date = date.fromisoformat(end_date_str) if end_date_str else None

        if start_date and end_date and start_date > end_date:
            raise CommandError(f"start_date ({start_date}) cannot be after end_date ({end_date}).")

        self.stdout.write("=" * 80)
        self.stdout.write("NOMAD ANALYST — HISTORICAL F&O PARQUET DOWNLOADER")
        self.stdout.write(f"Source Dataset: {HF_REPO_ID} ({LICENSE_NAME})")
        self.stdout.write(f"Target Directory: {output_dir}")
        if start_date or end_date:
            self.stdout.write(f"Requested Window: {start_date or 'Earliest'} to {end_date or 'Latest'}")
        if dry_run:
            self.stdout.write(self.style.WARNING("Mode: DRY-RUN (no files will be downloaded)"))
        self.stdout.write("=" * 80)

        # 1. Fetch remote dataset manifest from Hugging Face
        remote_files = self._fetch_repo_file_list()
        self.stdout.write(f"Discovered {len(remote_files)} total files in Hugging Face repository.")

        # 2. Plan files to download
        files_to_download: List[Dict[str, Any]] = []

        # (a) Index file
        if not skip_index:
            index_rpath = f"index/{symbol}.parquet"
            if index_rpath in remote_files:
                files_to_download.append({
                    "type": "index",
                    "rfilename": index_rpath,
                    "target_subpath": Path("index") / f"{symbol}.parquet",
                })
            else:
                self.stdout.write(self.style.WARNING(f"Index file {index_rpath} not found in remote repo."))

        # (b) Option expiry files
        if not index_only:
            option_files = [f for f in remote_files if f.startswith(f"options/{symbol}/")]
            matched_options = self._filter_option_files(
                option_files=option_files,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                single_expiry=single_expiry,
            )
            for rpath in matched_options:
                filename = Path(rpath).name
                files_to_download.append({
                    "type": "option",
                    "rfilename": rpath,
                    "target_subpath": Path("options") / filename,
                })

        if not files_to_download:
            self.stdout.write(self.style.WARNING("No matching historical files found for requested criteria."))
            return

        self.stdout.write(f"\nPlanned downloads: {len(files_to_download)} files:")
        for item in files_to_download:
            self.stdout.write(f"  [{item['type'].upper():6s}] {item['rfilename']} -> {item['target_subpath']}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\n[DRY RUN COMPLETE] No files written."))
            return

        # 3. Ensure local directory structure exists
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "index").mkdir(exist_ok=True)
        (output_dir / "options").mkdir(exist_ok=True)

        # 4. Load or initialize manifest.json
        manifest = self._load_manifest(output_dir)

        # 5. Download files with retry, atomic rename, and checksum verification
        downloaded_count = 0
        skipped_count = 0
        failed_count = 0

        for item in files_to_download:
            target_path = output_dir / item["target_subpath"]
            rfilename = item["rfilename"]
            download_url = f"{HF_RAW_BASE}/{rfilename}"

            # Check if file already exists and is valid in manifest
            manifest_entry = manifest.get("files", {}).get(rfilename)
            if not force and target_path.exists() and manifest_entry:
                if self._verify_checksum(target_path, manifest_entry.get("sha256")):
                    self.stdout.write(f"  [SKIPPED] {target_path.name} (valid in manifest)")
                    skipped_count += 1
                    continue

            self.stdout.write(f"  [DOWNLOADING] {rfilename}...")
            success, sha256_hash, file_size = self._download_with_retry(
                url=download_url,
                target_path=target_path,
                max_retries=max_retries,
            )

            if success:
                downloaded_count += 1
                coverage_info = self._extract_file_coverage(target_path)
                manifest.setdefault("files", {})[rfilename] = {
                    "local_path": str(item["target_subpath"]),
                    "file_type": item["type"],
                    "sha256": sha256_hash,
                    "size_bytes": file_size,
                    "downloaded_at_utc": datetime.now(zoneinfo.ZoneInfo("UTC")).isoformat(),
                    "source_url": download_url,
                    "row_count": coverage_info.get("row_count"),
                    "min_trading_day": coverage_info.get("min_trading_day"),
                    "max_trading_day": coverage_info.get("max_trading_day"),
                }
                self._save_manifest(output_dir, manifest)
                self.stdout.write(self.style.SUCCESS(f"    -> Saved {target_path.name} ({file_size:,} bytes, {coverage_info.get('row_count', 0):,} rows, sha256:{sha256_hash[:8]}...)"))
            else:
                failed_count += 1
                self.stdout.write(self.style.ERROR(f"    -> FAILED downloading {rfilename} after {max_retries} retries."))

        # 6. Final Summary
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write("HISTORICAL DOWNLOAD SUMMARY:")
        self.stdout.write(f"- Downloaded: {downloaded_count}")
        self.stdout.write(f"- Skipped (Already Valid): {skipped_count}")
        self.stdout.write(f"- Failed: {failed_count}")
        self.stdout.write(f"- Manifest: {output_dir / 'manifest.json'}")
        self.stdout.write("=" * 80)

        if failed_count > 0:
            raise CommandError(f"{failed_count} file(s) failed to download.")

    def _fetch_repo_file_list(self) -> List[str]:
        req = urllib.request.Request(HF_API_URL, headers={"User-Agent": "NomadAnalyst/1.0"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    data = json.loads(resp.read().decode())
                    return [s["rfilename"] for s in data.get("siblings", [])]
            except Exception as e:
                logger.warning("Attempt %d to query Hugging Face API failed: %s", attempt + 1, e)
                if attempt == 4:
                    raise CommandError(f"Failed to query Hugging Face repo {HF_REPO_ID}: {e}")
                time.sleep(2 ** attempt)
        return []

    def _filter_option_files(
        self,
        option_files: List[str],
        symbol: str,
        start_date: Optional[date],
        end_date: Optional[date],
        single_expiry: Optional[str],
    ) -> List[str]:
        """
        Filters option files based on requested dates and single expiry.
        Note: An option expiry file contains trading bars for multiple weeks preceding its expiry date.
        """
        matched: List[str] = []
        for rpath in sorted(option_files):
            # Format: options/NIFTY/YYYY-MM-DD.parquet
            stem = Path(rpath).stem
            try:
                exp_date = date.fromisoformat(stem)
            except ValueError:
                continue

            if single_expiry:
                if stem == single_expiry:
                    matched.append(rpath)
                continue

            # If start_date is set, options expire on or after start_date
            if start_date and exp_date < start_date:
                continue

            # If end_date is set, don't download options expiring excessively far after end_date
            # (allow up to 45 days after end_date to capture active trading in the window)
            if end_date and exp_date > (end_date + timedelta(days=45)):
                continue

            matched.append(rpath)

        return matched

    def _download_with_retry(
        self,
        url: str,
        target_path: Path,
        max_retries: int,
    ) -> Tuple[bool, str, int]:
        """
        Downloads a remote URL to target_path using an atomic temp file and retries.
        Returns: (success, sha256_hash, file_size)
        """
        temp_path = target_path.with_suffix(".tmp")
        req = urllib.request.Request(url, headers={"User-Agent": "NomadAnalyst/1.0"})

        for attempt in range(1, max_retries + 1):
            hasher = hashlib.sha256()
            total_bytes = 0
            try:
                with urllib.request.urlopen(req, timeout=60) as resp, open(temp_path, "wb") as f_out:
                    while True:
                        chunk = resp.read(65536)
                        if not chunk:
                            break
                        f_out.write(chunk)
                        hasher.update(chunk)
                        total_bytes += len(chunk)
                    f_out.flush()

                # Atomic replacement
                temp_path.replace(target_path)
                return True, hasher.hexdigest(), total_bytes

            except Exception as e:
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                    except OSError:
                        pass
                logger.warning("Download error on %s (attempt %d/%d): %s", url, attempt, max_retries, e)
                if attempt < max_retries:
                    backoff = 2 ** (attempt - 1)
                    time.sleep(backoff)

        return False, "", 0

    def _verify_checksum(self, path: Path, expected_sha256: Optional[str]) -> bool:
        if not expected_sha256 or not path.exists():
            return False
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest() == expected_sha256

    def _extract_file_coverage(self, path: Path) -> Dict[str, Any]:
        """Extracts row count and trading day coverage from Parquet metadata or column."""
        try:
            import pyarrow.parquet as pq
            meta = pq.read_metadata(path)
            num_rows = meta.num_rows

            # Fast path: check column chunk statistics
            min_day = None
            max_day = None
            col_indices = [
                i for i in range(meta.num_columns)
                if meta.row_group(0).column(i).path_in_schema == "trading_day"
            ]
            if col_indices:
                idx = col_indices[0]
                min_candidates = [
                    meta.row_group(r).column(idx).statistics.min
                    for r in range(meta.num_row_groups)
                    if meta.row_group(r).column(idx).statistics and meta.row_group(r).column(idx).statistics.min
                ]
                max_candidates = [
                    meta.row_group(r).column(idx).statistics.max
                    for r in range(meta.num_row_groups)
                    if meta.row_group(r).column(idx).statistics and meta.row_group(r).column(idx).statistics.max
                ]
                if min_candidates and max_candidates:
                    min_day = min(min_candidates)
                    max_day = max(max_candidates)

            # Fallback path if stats are not present in metadata
            if min_day is None or max_day is None:
                table = pq.read_table(path, columns=["trading_day"])
                days = table["trading_day"].to_pylist()
                if days:
                    min_day = min(days)
                    max_day = max(days)

            return {
                "row_count": num_rows,
                "min_trading_day": str(min_day) if min_day else None,
                "max_trading_day": str(max_day) if max_day else None,
            }
        except Exception as e:
            logger.warning("Could not extract coverage for %s: %s", path, e)
            return {"row_count": 0, "min_trading_day": None, "max_trading_day": None}

    def _load_manifest(self, output_dir: Path) -> Dict[str, Any]:
        manifest_path = output_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "dataset_id": HF_REPO_ID,
            "license": LICENSE_NAME,
            "license_url": LICENSE_URL,
            "attribution": (
                "Data sourced from thetrademarkk/india-index-options-1m on Hugging Face. "
                "Licensed under Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0). "
                "For personal research and paper trading only. No commercial use."
            ),
            "updated_at_utc": datetime.now(zoneinfo.ZoneInfo("UTC")).isoformat(),
            "files": {},
        }

    def _save_manifest(self, output_dir: Path, manifest: Dict[str, Any]) -> None:
        manifest["updated_at_utc"] = datetime.now(zoneinfo.ZoneInfo("UTC")).isoformat()
        manifest_path = output_dir / "manifest.json"
        temp_path = manifest_path.with_suffix(".tmp")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        temp_path.replace(manifest_path)
