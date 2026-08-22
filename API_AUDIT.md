# API Architecture Audit

This document inventories and details all REST API, WebSocket endpoints, serializers, and schema specifications in the **Nomad Analyst Platform** as of Module 0.

---

## 1. REST Endpoints Inventory

### Endpoint: `/api/chat/`
*   **Method**: `POST`
*   **Purpose**: Dispatch prompts to the agent reasoning system.
*   **Serializer**:
    *   `ChatRequestSerializer` (Input):
        *   `message`: String (required).
        *   `conversation_id`: UUID (optional).
        *   `agent_type`: String (default `"ResearchAgent"`).
        *   `async_execution`: Boolean (default `False`).
        *   `selected_provider`: String (optional).
    *   `ChatResponseSerializer` (Output):
        *   `conversation_id`: UUID string.
        *   `response`: String (assistant reply).
        *   `selected_provider`: String.
        *   `selected_model`: String.
        *   `prompt_tokens`: Integer.
        *   `completion_tokens`: Integer.
        *   `total_tokens`: Integer.
*   **Request Types**:
    *   *Synchronous*: Returns `HTTP_200_OK` with the complete response payload.
    *   *Asynchronous*: Returns `HTTP_202_ACCEPTED` with a Celery `task_id` and `status: Accepted` immediately.

### Endpoint: `/api/chat/approve/`
*   **Method**: `POST`
*   **Purpose**: Inject human approval signals into a paused LangGraph thread checkpointer state.
*   **Request Parameters**:
    *   `conversation_id`: UUID string.
    *   `approved`: Boolean.
*   **Response Payload**:
    *   `status`: `"Resumed"` or `"Rejected"`.
    *   `task_id`: UUID string (if resumed).

### Endpoint: `/api/conversations/`
*   **Method**: `GET`
*   **Purpose**: List all historical conversation threads for the default user profile.
*   **Response Payload**: List of JSON objects (id, title, selected_provider, selected_model, created_at, updated_at).

### Endpoint: `/api/conversations/<uuid:conversation_id>/`
*   **Method**: `GET`
*   **Purpose**: Retrieve the chronological log of messages associated with a conversation thread.
*   **Response Payload**: Details including message array (role, content, tokens, provider, model, timestamp).

### Endpoint: `/api/providers/`
*   **Method**: `GET`
*   **Purpose**: List configured LLM model providers and their health statuses.

### Endpoint: `/api/analytics/`
*   **Method**: `GET`
*   **Purpose**: Retrieve token expenditures and cost summaries from the telemetry SQLite DB.

---

## 2. WebSocket Endpoints Inventory

### Path: `/ws/chat/<uuid:conversation_id>/`
*   **Consumer Class**: `chat.consumers.ChatConsumer`
*   **Purpose**: Bi-directional real-time communication of agent execution logs and token streams.
*   **Outgoing Event Streams**:
    *   `planner_start`: Fired when high-level plan construction is initiated.
    *   `planner_plan`: Streams the list of plan goals.
    *   `executor_step_start`: Streams current step index and goal name.
    *   `tool_execution`: Streams tool name, arguments, results, and status.
    *   `critic_start`: Fired when reflection critic starts.
    *   `critic_pass` / `critic_fail`: Streams critic result and reasons.
    *   `report_synthesized`: Streams the final markdown investment research report.
    *   `run_completed`: Fired when agent graph completes execution.
