import logging
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Any
from market.exceptions import ProviderConnectionError

logger = logging.getLogger(__name__)

class YahooRSSNewsProvider:
    """
    Ingests public XML RSS headline feeds from Yahoo Finance for a stock symbol.
    """

    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        )

    def fetch_company_news(self, symbol: str) -> List[Dict[str, Any]]:
        """
        Fetches the RSS headlines from Yahoo Finance for the target symbol.
        Returns a list of raw items dictionary.
        """
        # Upper symbol clean
        upper_symbol = symbol.strip().upper()
        # Add .NS suffix if not present
        if not upper_symbol.endswith(".NS") and not upper_symbol.endswith(".BO") and "." not in upper_symbol:
            query_symbol = f"{upper_symbol}.NS"
        else:
            query_symbol = upper_symbol

        url = f"https://finance.yahoo.com/rss/headline?s={query_symbol}"
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/xml, text/xml, */*"
        }

        logger.info(f"YahooRSSNewsProvider: fetching news for symbol '{query_symbol}' from URL: {url}")

        try:
            response = requests.get(url, headers=headers, timeout=15)
        except requests.exceptions.RequestException as err:
            logger.error(f"YahooRSSNewsProvider: failed to fetch news for {query_symbol}: {err}")
            raise ProviderConnectionError(f"News provider connection failed: {err}")

        if response.status_code != 200:
            logger.error(f"YahooRSSNewsProvider: status {response.status_code} for {query_symbol}")
            raise ProviderConnectionError(f"News provider returned HTTP status {response.status_code}")

        return self.parse_rss_xml(response.text)

    def parse_rss_xml(self, xml_content: str) -> List[Dict[str, Any]]:
        """
        Parses XML string into raw dictionaries of RSS items.
        """
        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as p_err:
            logger.error(f"YahooRSSNewsProvider: XML parse error: {p_err}")
            return []

        channel = root.find("channel")
        if channel is None:
            return []

        items = []
        for item in channel.findall("item"):
            title_node = item.find("title")
            link_node = item.find("link")
            desc_node = item.find("description")
            pub_node = item.find("pubDate")
            guid_node = item.find("guid")

            headline = title_node.text.strip() if title_node is not None and title_node.text else ""
            url = link_node.text.strip() if link_node is not None and link_node.text else ""
            summary = desc_node.text.strip() if desc_node is not None and desc_node.text else ""
            pub_date = pub_node.text.strip() if pub_node is not None and pub_node.text else ""
            source_id = guid_node.text.strip() if guid_node is not None and guid_node.text else ""

            if not headline:
                # Validation: skip empty headlines
                continue

            items.append({
                "headline": headline,
                "summary": summary,
                "url": url,
                "source_id": source_id,
                "published_at_raw": pub_date,
                "source": "yahoo_rss"
            })

        return items
