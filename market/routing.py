"""
WebSocket routing patterns for market app.
"""

from django.urls import re_path
from market.consumers import IntradayMarketConsumer

websocket_urlpatterns = [
    re_path(r"^ws/intraday/$", IntradayMarketConsumer.as_asgi()),
]
