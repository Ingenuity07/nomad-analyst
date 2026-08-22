from abc import ABC, abstractmethod
from typing import Dict, Any
from market.providers.base import MarketQuote

class BaseNormalizer(ABC):
    """
    Abstract base class for converting provider-specific quote structures
    into the canonical internal MarketQuote representation.
    """
    
    @abstractmethod
    def normalize(self, raw_data: Dict[str, Any]) -> MarketQuote:
        pass
