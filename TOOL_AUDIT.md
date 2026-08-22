# Tool Architecture & Inventory Audit

This document lists and audits all LLM tools registered in the **Nomad Analyst Platform** as of Module 0.

---

## 1. Tool Inventory Table

| Tool Name | Class Name | Purpose | Input Schema | Output Schema | Classification |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`read_file`** | `FileTool` | Reads local workspace files. | `file_path` (string) | Raw file text content | **KEEP** |
| **`search_web`** | `SearchWebTool` | Searches the web using Google/Tavily. | `query` (string) | JSON list of search results | **KEEP** |
| **`crawl_website`** | `CrawlWebsiteTool` | Scrapes webpage text content via Playwright. | `url` (string) | Cleaned webpage text body | **KEEP** |
| **`get_stock_snapshot`** | `GetStockSnapshotTool` | Fetches stock price, daily high/low, and changes. | `symbol` (string) | Structured JSON market quote details | **KEEP** |
| **`analyze_screenshot`** | `AnalyzeScreenshotTool` | Inspects screenshots using multimodal vision. | `screenshot_path`, `prompt` | Textual analysis of image | **KEEP** |

---

## 2. Detailed Tool Audits

### 1. `get_stock_snapshot`
*   **Purpose**: Decoupled tool wrapper that interfaces directly with the operational database and data service plane. It allows the agent to fetch point-in-time ticker values without executing raw database SQL commands.
*   **Implementation**: Resolves the request by instantiating `MarketService()` which fetches the quote, normalizes it, updates PostgreSQL operational tables, and returns the canonical structured dictionary.
*   **Dependencies**: `market.services.market_service.MarketService`.
*   **Error Handling**: Catches exceptions and returns them as a structured `ToolError` with failure codes (`EXECUTION_ERROR`) to prevent agent runtime crashes.

### 2. `crawl_website`
*   **Purpose**: Deep scraping tool allowing the agent to parse corporate reports or financial articles.
*   **Implementation**: Utilizes Playwright to navigate to pages and BeautifulSoup to strip boilerplate HTML.
*   **Safety Guards**: The URL validation filter runs *before* Playwright spawns, blocking navigations to `file://` protocols, loopbacks (`localhost`, `127.0.0.1`), or cloud metadata endpoints (`169.254.169.254`) to prevent Server-Side Request Forgery (SSRF) or local file read leaks.
*   **Dependencies**: `playwright`, `beautifulsoup4`.

### 3. `analyze_screenshot`
*   **Purpose**: Inspects screenshots captured during page navigation or visual tasks.
*   **Implementation**: Reads the target file, base64 encodes it, and sends the payload to Gemini's vision endpoint.
*   **Dependencies**: Gemini vision model configuration.
