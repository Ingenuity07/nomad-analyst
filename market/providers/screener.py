import logging
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from typing import Dict, Any, List
import re
from market.exceptions import (
    ProviderConnectionError,
    SymbolNotFoundError,
    InvalidPayloadError
)

logger = logging.getLogger(__name__)

class ScreenerFundamentalProvider:
    """
    HTML scraper fundamental data provider that queries Screener.in consolidated pages.
    Extracts quarterly results, profit-loss (annual income statement), balance sheet,
    and cash flows tables.
    """
    
    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    def get_fundamental_data(self, symbol: str) -> Dict[str, Any]:
        """
        Queries Screener.in for the target symbol and parses consolidated tables.
        Returns a raw payload dictionary containing quarters, profit_loss, balance_sheet, and cash_flow datasets.
        """
        # Upper symbol clean
        upper_symbol = symbol.strip().upper()
        # Suffix strip if present (e.g. RELIANCE.NS -> RELIANCE)
        clean_symbol = upper_symbol.split('.')[0]
        
        # Screener URL target
        url = f"https://www.screener.in/company/{clean_symbol}/consolidated/"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html"
        }

        logger.info(f"ScreenerProvider: requesting financials for symbol '{clean_symbol}' via url {url}")

        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.exceptions.Timeout as t_err:
            logger.error(f"ScreenerProvider: connection timed out for {clean_symbol}: {t_err}")
            raise ProviderConnectionError(f"Connection timed out for symbol '{symbol}': {t_err}")
        except requests.exceptions.RequestException as r_err:
            logger.error(f"ScreenerProvider: request exception for {clean_symbol}: {r_err}")
            raise ProviderConnectionError(f"Provider connection error: {r_err}")

        # Check HTTP status
        if response.status_code == 404:
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found on Screener (404).")
        elif response.status_code != 200:
            raise ProviderConnectionError(f"Screener returned HTTP status {response.status_code}.")

        html_content = response.text
        return self.parse_html(html_content, clean_symbol, url)

    def parse_html(self, html_content: str, symbol: str, source_url: str) -> Dict[str, Any]:
        """
        Parses raw HTML structure into raw statement dictionaries.
        """
        soup = BeautifulSoup(html_content, "html.parser")
        
        # Check if the page is a valid Screener company page
        if not soup.find("section", id="quarters") and not soup.find("section", id="profit-loss"):
            raise SymbolNotFoundError(f"Failed to find financials on the retrieved page for symbol '{symbol}'.")

        data = {
            "symbol": symbol,
            "source": "screener",
            "source_url": source_url,
            "retrieved_at": datetime.now(timezone.utc).isoformat() if 'datetime' in globals() else None,
            "quarters": self.parse_table(soup, "quarters"),
            "profit_loss": self.parse_table(soup, "profit-loss"),
            "balance_sheet": self.parse_table(soup, "balance-sheet"),
            "cash_flow": self.parse_table(soup, "cash-flow")
        }
        
        return data

    def parse_table(self, soup: BeautifulSoup, section_id: str) -> Dict[str, Any]:
        """
        Parses a Screener table inside a section.
        Returns a dict mapping: row_label -> list of {period: val} or list of raw strings.
        """
        section = soup.find("section", id=section_id)
        if not section:
            return {}
            
        table = section.find("table")
        if not table:
            return {}
            
        # Parse headers (columns)
        headers = []
        for th in table.find_all("th"):
            txt = th.text.strip()
            # Clean header spaces/pluses
            txt = re.sub(r'\s+', ' ', txt)
            headers.append(txt)
            
        if not headers:
            return {}
            
        # First column is row label, subsequent are periods
        periods = headers[1:]
        
        rows_data = {}
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            if not tds:
                continue
                
            row_label = tds[0].text.strip()
            # Clean label (e.g. "Sales +" -> "Sales", remove trailing characters)
            row_label = re.sub(r'[\+\s]+$', '', row_label).strip()
            row_label = re.sub(r'\s+', ' ', row_label)
            
            row_values = []
            for i, td in enumerate(tds[1:]):
                if i >= len(periods):
                    break
                val_txt = td.text.strip().replace(",", "")
                # Parse numeric values
                val = None
                if val_txt == "" or val_txt == "-" or val_txt == "—":
                    val = None
                else:
                    # Clean percentage sign
                    val_txt = val_txt.replace("%", "")
                    try:
                        val = float(val_txt)
                    except ValueError:
                        val = None
                        
                row_values.append({
                    "period": periods[i],
                    "value": val
                })
                
            rows_data[row_label] = row_values
            
        return {
            "periods": periods,
            "rows": rows_data
        }
