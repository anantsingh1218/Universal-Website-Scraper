# Universal Website Scraper

A universal website scraper (MVP) that handles both static and JavaScript-rendered content, with support for click flows, scrolling, and pagination. Includes a web-based JSON viewer frontend.

## Features

- **Static Scraping**: Fast scraping using `httpx` and `selectolax` for static HTML content
- **JS Rendering Fallback**: Automatic fallback to Playwright for JavaScript-heavy pages
- **Interactive Scraping**: Supports clicking tabs, "Load more" buttons, and scrolling
- **Pagination**: Handles pagination links up to depth ≥ 3
- **Section Parsing**: Intelligently groups content into sections (hero, nav, footer, etc.)
- **Noise Filtering**: Filters out cookie banners, modals, and overlays
- **Web UI**: Simple, clean interface to input URLs and view/download scraped data

## Tech Stack

- **Backend**: FastAPI
- **Static Scraping**: httpx + selectolax
- **JS Rendering**: Playwright
- **Frontend**: Jinja2 templates
- **Server**: uvicorn

## Setup & Run

### Prerequisites

- Python 3.10 or higher
- Internet connection (for installing dependencies and scraping)

### Quick Start

1. Make the run script executable:
   ```bash
   chmod +x run.sh
   ```

2. Run the setup and start the server:
   ```bash
   ./run.sh
   ```

The script will:
- Create a virtual environment (if needed)
- Install all dependencies
- Install Playwright browsers
- Start the server on `http://localhost:8000`

### Manual Setup (Alternative)

If you prefer to set up manually:

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run the server
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Usage

### Web Interface

1. Open your browser and navigate to `http://localhost:8000`
2. Enter a URL in the input box
3. Click "Scrape" to start scraping
4. View the results in the expandable sections
5. Download the full JSON using the "Download JSON" button

### API Endpoints

#### Health Check
```bash
GET /healthz
```

Response:
```json
{
  "status": "ok"
}
```

#### Scrape URL
```bash
POST /scrape
Content-Type: application/json

{
  "url": "https://example.com"
}
```

Response: See the schema in the assignment specification.

## Test URLs

The following URLs were used for testing:

1. **https://en.wikipedia.org/wiki/Artificial_intelligence**
   - Static page with rich content
   - Tests basic static scraping and section parsing
   - Good for testing meta extraction and link handling

2. **https://vercel.com/**
   - JS-heavy marketing page with dynamic content
   - Tests JS rendering fallback
   - Contains tabs and interactive elements

3. **https://news.ycombinator.com/**
   - Pagination-based content
   - Tests pagination link following
   - Good for testing depth ≥ 3 requirement

## Project Structure

```
.
├── app.py                 # FastAPI application
├── scraper.py             # Core scraping logic
├── requirements.txt       # Python dependencies
├── run.sh                 # Setup and run script
├── README.md              # This file
├── design_notes.md        # Design decisions and strategies
├── capabilities.json      # Feature capabilities
└── templates/
    └── index.html         # Frontend UI template
```

## Known Limitations

1. **Single Domain**: The scraper focuses on the same origin (single domain) for simplicity. Cross-domain navigation is limited.

2. **Timeout Handling**: Some sites may block automation or take longer than expected. Errors are captured in the `errors` array.

3. **Content Limits**: To prevent excessive memory usage:
   - Sections are limited to 20 per page
   - Text content is truncated to 5000 characters per section
   - Links are limited to 50 per section
   - Images are limited to 20 per section

4. **Browser Resources**: Playwright launches a headless Chromium browser, which requires system resources. Multiple concurrent requests may impact performance.

5. **Rate Limiting**: The scraper does not implement rate limiting. Be respectful when scraping external sites.

## Error Handling

Errors are captured and returned in the `errors` array with:
- `message`: Description of the error
- `phase`: Phase where error occurred (`fetch`, `render`, `parse`, etc.)

The scraper attempts to return partial results even when errors occur, rather than failing completely.

## License

This project is created for assignment purposes.
