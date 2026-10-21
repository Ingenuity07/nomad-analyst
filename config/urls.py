from django.contrib import admin
from django.urls import path, include
from django.views.generic import TemplateView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # OpenAPI Schema & API Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    path('api/schema/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),

    # Versioned REST API presentation layer (v1)
    path('api/v1/', include('market.urls')),
    path('api/v1/fno/', include('fno.urls')),

    # Zerodha Kite OAuth root callback (matches registered redirect URL)
    path('kite/callback/', include([
        path('', __import__('market.views', fromlist=['KiteCallbackView']).KiteCallbackView.as_view(), name='kite-callback-root'),
    ])),

    # Legacy Chat API (now inside chat app)
    path('api/', include('chat.urls')),
    
    # LLM Providers status API (now inside llm app)
    path('api/', include('llm.urls')),
    
    path('', TemplateView.as_view(template_name='chat.html'), name='chat_ui'),
]
