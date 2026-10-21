"""
Nomad Analyst — F&O Presentation Layer URL Routing
Reference: Phase FNO-1 Implementation
"""

from django.urls import path
from fno.views import (
    FnoOverviewAPIView,
    FnoStrategyAPIView,
    FnoTradesAPIView,
    FnoDiagnosticsAPIView,
)

urlpatterns = [
    path('overview/', FnoOverviewAPIView.as_view(), name='api-fno-overview'),
    path('strategy/', FnoStrategyAPIView.as_view(), name='api-fno-strategy'),
    path('trades/', FnoTradesAPIView.as_view(), name='api-fno-trades'),
    path('diagnostics/', FnoDiagnosticsAPIView.as_view(), name='api-fno-diagnostics'),
]
