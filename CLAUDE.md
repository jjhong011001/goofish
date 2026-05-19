# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Xianyu Scraper**: A CLI and web-based search tool for goofish.com (Alibaba's Xianyu second-hand marketplace). It automates login, performs product searches, and exports results to CSV or Excel with price analytics.

## Architecture

### Core Components

1. **CLI Tool (`main.py`)**: Click-based CLI with two commands:
   - `login`: Opens browser for authentication, saves session to `session/storage_state.json`
   - `search`: Queries Xianyu, exports results, displays price statistics

2. **Web Server (`server.py`)**: FastAPI application with SSE (Server-Sent Events) streaming:
   - `/` - Serves static HTML UI
   - `/api/status` - Session validity check
   - `/api/login` - Browser login via SSE stream
   - `/api/search` - Search with real-time progress
   - `/api/export/{job_id}` - Download search results

3. **Scraper Module** (`scraper/`):
   - **auth.py**: Session management using Playwright (browser context save/load)
   - **search.py**: Network interception to capture mtop API responses across multiple pages
   - **parser.py**: Extracts flat item records from deeply nested JSON API responses
   - **exporter.py**: Exports to CSV/Excel using pandas, with customizable field selection

### Data Flow

1. User authenticates via Playwright browser → session stored as `session/storage_state.json`
2. Search request triggers Playwright to visit search URL with saved session
3. Network interceptor captures all JSON responses (specifically mtop API responses)
4. Parser extracts items from response structure: `data.resultList[].data.item.main`
5. Exporter creates CSV/Excel files in `data/` directory

## Development

### Setup
```bash
pip install -r requirements.txt
```

### Common Commands

**CLI Usage:**
```bash
# Initial login (opens browser window)
python main.py login

# Search and export (creates CSV in data/)
python main.py search "iPhone 15"

# Search with options
python main.py search "MacBook" --pages 5 --format excel --fields "title,price,location"

# Search with location filter
python main.py search "iPhone" --location "北京,上海"

# Debug mode (prints raw API responses)
python main.py search "AirPods" --debug
```

**Web Server:**
```bash
# Run development server (http://localhost:8000)
uvicorn server:app --reload
```

### Key Configuration

- **Session File**: `session/storage_state.json` - required for authenticated requests
- **Export Directory**: `data/` - contains generated CSV/Excel files
- **Available Fields**: `item_id`, `title`, `price`, `condition`, `seller_nick`, `location`, `category`, `want_count`, `created_time`, `images` (see `scraper/search.py` and `scraper/exporter.py`)

### Important Implementation Details

- **Session Validation**: Checks for both `_m_h5_tk` token and `unb` user ID cookies
- **Search API**: Intercepts responses from `mtop.taobao.idlemtopsearch.pc.search` endpoint specifically
- **Rate Limiting**: Configurable delays between pages (default 1.5-3.0 seconds) to avoid blocking
- **Concurrent Requests**: Web server uses `asyncio.Lock()` to prevent concurrent browser sessions
- **Price Parsing**: Handles price strings with currency symbol (￥) and comma formatting

## Dependencies

- **playwright**: Browser automation for login & search
- **pandas**: DataFrame operations for export
- **openpyxl**: Excel file writing
- **click**: CLI framework
- **fastapi + uvicorn**: Web server
- **rich**: Terminal UI formatting (tables, progress spinners)
