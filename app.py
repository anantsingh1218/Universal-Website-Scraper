"""
FastAPI application for universal website scraper.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn

from scraper import scrape_url

app = FastAPI(title="Universal Website Scraper")
templates = Jinja2Templates(directory="templates")


class ScrapeRequest(BaseModel):
    url: str


@app.get("/healthz")
async def healthz():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/scrape")
async def scrape(request: ScrapeRequest):
    """Scrape a URL and return structured JSON."""
    try:
        # Validate URL scheme
        if not request.url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=400,
                detail="Only http:// and https:// URLs are supported"
            )
        
        result = await scrape_url(request.url)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the frontend UI."""
    return templates.TemplateResponse("index.html", {"request": request})


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

