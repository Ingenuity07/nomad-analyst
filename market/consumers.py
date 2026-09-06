"""
Django Channels WebSocket Consumer for Intraday Market Context streaming.

Route: ws/intraday/
Group: intraday_market
"""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


class IntradayMarketConsumer(AsyncWebsocketConsumer):
    """
    Streams live intraday market context, breadth, regime, and constituent updates.
    """

    GROUP_NAME = "intraday_market"

    async def connect(self):
        await self.channel_layer.group_add(
            self.GROUP_NAME,
            self.channel_name
        )
        await self.accept()
        logger.info(f"WebSocket client connected to {self.GROUP_NAME} ({self.channel_name})")

        # Send initial context state immediately upon connection
        try:
            initial_data = await self._get_initial_context()
            await self.send(text_data=json.dumps({
                "type": "market_context_init",
                "data": initial_data,
            }))
            initial_opps = await self._get_initial_opportunities()
            await self.send(text_data=json.dumps({
                "type": "opportunity_init",
                "data": initial_opps,
            }))
        except Exception as e:
            logger.warning(f"Error sending initial WebSocket data: {e}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.GROUP_NAME,
            self.channel_name
        )
        logger.info(f"WebSocket client disconnected from {self.GROUP_NAME} ({self.channel_name}) code: {close_code}")

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handles incoming ping or filter requests from browser.
        """
        if text_data:
            try:
                msg = json.loads(text_data)
                if msg.get("action") == "ping":
                    await self.send(text_data=json.dumps({"type": "pong"}))
                elif msg.get("action") == "refresh":
                    data = await self._get_initial_context()
                    await self.send(text_data=json.dumps({
                        "type": "market_context_init",
                        "data": data,
                    }))
            except Exception as e:
                logger.error(f"Error handling incoming WS message: {e}")

    async def market_context_update(self, event):
        """
        Called when a 'market_context_update' event is dispatched to 'intraday_market' group.
        """
        await self.send(text_data=json.dumps({
            "type": "market_context_update",
            "data": event["data"]
        }))

    async def stock_context_update(self, event):
        """
        Called when a 'stock_context_update' event is dispatched to 'intraday_market' group.
        """
        await self.send(text_data=json.dumps({
            "type": "stock_context_update",
            "data": event["data"]
        }))

    async def opportunity_update(self, event):
        """
        Called when an 'opportunity_update' event is dispatched to 'intraday_market' group.
        """
        await self.send(text_data=json.dumps({
            "type": "opportunity_update",
            "data": event["data"]
        }))

    @sync_to_async
    def _get_initial_context(self):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        return mgr.compute_current_context()

    @sync_to_async
    def _get_initial_opportunities(self):
        from market.services.intraday_state_manager import IntradayStateManager
        mgr = IntradayStateManager()
        return mgr.compute_current_opportunities(limit=10)
