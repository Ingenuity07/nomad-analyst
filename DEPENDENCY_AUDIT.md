# Dependency Audit

This document classifies all third-party python dependencies defined in `requirements.txt` based on their role in the **Nomad Analyst Platform** as of Module 0.

---

## 1. Dependency Classifications

### CORE (Django Web Framework & APIs)
*   `Django==6.0.6`: Core web framework.
*   `django-cors-headers==4.9.0`: Manages Cross-Origin Resource Sharing (CORS) headers.
*   `djangorestframework==3.17.1`: REST API toolkit.
*   `drf-spectacular==0.30.0`: Swagger/OpenAPI documentation schema generator.
*   `asgiref==3.11.1`: ASGI utilities.

### INFRASTRUCTURE (Asynchronous Workers & Channels)
*   `celery==5.6.3`: Task queue library.
*   `django-celery-beat==2.9.0`: Database-backed Celery periodic task scheduler.
*   `redis==8.0.1`: Client library for Redis cache/broker.
*   `kombu==5.6.2`, `amqp==5.3.1`, `billiard==4.2.4`, `vine==5.1.0`: Underlying messaging transport for Celery.
*   `daphne==4.2.2`: ASGI server.
*   `channels==4.3.2`: Django channels ASGI core.
*   `channels_redis==4.3.0`: Redis channel layer backend for real-time WebSocket communication.

### AI / AGENTIC LAYER
*   `langgraph==1.2.8`: Orchestrator graph engine.
*   `langgraph-checkpoint==4.1.1`: State checkpoint interfaces.
*   `langgraph-prebuilt==1.1.0`, `langgraph-sdk==0.4.2`: Extended LangGraph packages.
*   `langchain-core==1.4.8`: Model/prompt abstractions.
*   `langsmith==0.10.17`: Tracing and agent testing dashboard.

### DATA LAYER (Crawlers & PDF Readers)
*   `playwright==1.61.0`: Browser automation framework.
*   `beautifulsoup4==4.15.0`, `soupsieve==2.9.1`, `lxml==6.1.1`: HTML scraping and cleaning tools.
*   `pypdf==6.14.2`: PDF reader library for corporate fillings.
*   `httpx==0.28.1`, `httpcore==1.0.9`, `h11==0.16.0`, `requests==2.34.2`, `requests-toolbelt==1.0.0`: HTTP clients.

### SECURITY & DECRYPT
*   `cryptography==49.0.0`, `pyOpenSSL==26.3.0`, `cffi==2.1.0`: Security primitives.

### DEVELOPMENT & SYSTEM UTILS
*   `cron-descriptor==1.4.5`, `python-crontab==3.3.0`: Cron string parsers.
*   `tzdata==2026.2`, `tzlocal==5.4.4`, `python-dateutil==2.9.0.post0`: Timezone management utilities.
*   `PyYAML==6.0.3`: YAML config parser.
*   `orjson==3.11.9`, `ujson==5.13.0`, `msgpack==1.2.1`: Serialization optimizers.
*   `pydantic==2.13.4`, `pydantic_core==2.46.4`: Data validation and schema models.
*   `greenlet==3.5.3`: Concurrency controls.
