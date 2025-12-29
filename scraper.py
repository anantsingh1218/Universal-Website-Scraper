"""
Core scraping logic with static and JS rendering support.
"""
import httpx
from selectolax.parser import HTMLParser
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PlaywrightTimeoutError
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
import re
import asyncio


class Scraper:
    """Main scraper class handling static and JS-rendered content."""
    
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        
    async def cleanup(self):
        """Clean up browser resources."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
            
    async def get_browser(self):
        """Lazy initialization of browser."""
        if self.browser is None:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
        return self.browser
        
    async def scrape(self, url: str) -> Dict[str, Any]:
        """
        Main scraping method with static-first, JS-fallback strategy.
        """
        errors = []
        scraped_at = datetime.now(timezone.utc).isoformat()
        interactions = {
            "clicks": [],
            "scrolls": 0,
            "pages": [url]
        }
        
        # Try static scraping first
        try:
            html, meta = await self._static_scrape(url)
            
            # Heuristic: if we got very little text content, try JS rendering
            parser = HTMLParser(html)
            text_content = parser.body.text() if parser.body else ""
            
            # If less than 200 chars of text or no main content sections, try JS
            if len(text_content.strip()) < 200 or not self._has_main_content(html):
                html, meta, js_errors, js_interactions = await self._js_scrape(url)
                errors.extend(js_errors)
                interactions.update(js_interactions)
            else:
                # Still try JS for interactions (clicks, scrolls)
                html, meta, js_errors, js_interactions = await self._js_scrape_for_interactions(url)
                errors.extend(js_errors)
                interactions.update(js_interactions)
        except Exception as e:
            errors.append({"message": f"Static scrape failed: {str(e)}", "phase": "fetch"})
            # Fallback to JS
            try:
                html, meta, js_errors, js_interactions = await self._js_scrape(url)
                errors.extend(js_errors)
                interactions.update(js_interactions)
            except Exception as e2:
                errors.append({"message": f"JS scrape failed: {str(e2)}", "phase": "render"})
                html = ""
                meta = self._extract_meta_static("")
        
        # Parse sections
        sections = self._parse_sections(html, url)
        
        return {
            "url": url,
            "scrapedAt": scraped_at,
            "meta": meta,
            "sections": sections,
            "interactions": interactions,
            "errors": errors
        }
    
    def _has_main_content(self, html: str) -> bool:
        """Check if HTML has substantial main content."""
        parser = HTMLParser(html)
        main = parser.css_first("main")
        if main:
            return len(main.text().strip()) > 100
        # Check for article or substantial content
        article = parser.css_first("article")
        if article:
            return len(article.text().strip()) > 100
        return False
    
    async def _static_scrape(self, url: str) -> tuple[str, Dict[str, str]]:
        """Static scraping using httpx."""
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text
            meta = self._extract_meta_static(html)
            return html, meta
    
    async def _js_scrape(self, url: str) -> tuple[str, Dict[str, str], List[Dict[str, str]], Dict[str, Any]]:
        """JS rendering using Playwright."""
        errors = []
        interactions = {
            "clicks": [],
            "scrolls": 0,
            "pages": [url]
        }
        browser = await self.get_browser()
        page = await browser.new_page()
        
        try:
            # Navigate and wait
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)  # Additional wait for dynamic content
            
            # Extract HTML and meta
            html = await page.content()
            meta = await self._extract_meta_js(page)
            
            await page.close()
            return html, meta, errors, interactions
        except PlaywrightTimeoutError as e:
            errors.append({"message": f"Timeout waiting for page load: {str(e)}", "phase": "render"})
            html = await page.content()
            meta = await self._extract_meta_js(page)
            await page.close()
            return html, meta, errors, interactions
        except Exception as e:
            errors.append({"message": f"JS rendering error: {str(e)}", "phase": "render"})
            try:
                html = await page.content()
                meta = await self._extract_meta_js(page)
            except:
                html = ""
                meta = self._extract_meta_static("")
            await page.close()
            return html, meta, errors, interactions
    
    async def _js_scrape_for_interactions(self, url: str) -> tuple[str, Dict[str, str], List[Dict[str, str]], Dict[str, Any]]:
        """JS scraping with interactions (clicks, scrolls, pagination)."""
        errors = []
        browser = await self.get_browser()
        page = await browser.new_page()
        
        clicks = []
        scrolls = 0
        pages_visited = [url]
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            
            # Try clicking tabs
            tabs = await page.query_selector_all('[role="tab"], .tab, [data-tab]')
            for tab in tabs[:3]:  # Limit to 3 tabs
                try:
                    await tab.click(timeout=5000)
                    await asyncio.sleep(1)
                    clicks.append('[role="tab"]')
                except:
                    pass
            
            # Try clicking "Load more" / "Show more" buttons
            load_more_selectors = [
                'button:has-text("Load more")',
                'button:has-text("Show more")',
                'button:has-text("Load More")',
                'a:has-text("Load more")',
                '[class*="load-more"]',
                '[class*="show-more"]'
            ]
            
            for selector in load_more_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button:
                        await button.click(timeout=5000)
                        await asyncio.sleep(2)
                        clicks.append(selector)
                        break
                except:
                    pass
            
            # Scroll and pagination to depth ≥ 3
            for i in range(3):
                # Scroll down
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await asyncio.sleep(1.5)
                scrolls += 1
                
                # Check for pagination links
                next_links = await page.query_selector_all('a:has-text("Next"), a:has-text("next"), [rel="next"]')
                if next_links and i < 2:  # Don't go beyond depth 3
                    try:
                        next_url = await next_links[0].get_attribute("href")
                        if next_url:
                            full_url = urljoin(url, next_url)
                            if full_url not in pages_visited:
                                pages_visited.append(full_url)
                                await page.goto(full_url, wait_until="networkidle", timeout=30000)
                                await asyncio.sleep(2)
                    except:
                        pass
            
            html = await page.content()
            meta = await self._extract_meta_js(page)
            
            interactions = {
                "clicks": clicks,
                "scrolls": scrolls,
                "pages": pages_visited
            }
            
            await page.close()
            return html, meta, errors, interactions
        except Exception as e:
            errors.append({"message": f"Interaction error: {str(e)}", "phase": "render"})
            try:
                html = await page.content()
                meta = await self._extract_meta_js(page)
            except:
                html = ""
                meta = self._extract_meta_static("")
            interactions = {
                "clicks": clicks,
                "scrolls": scrolls,
                "pages": pages_visited
            }
            await page.close()
            return html, meta, errors, interactions
    
    def _extract_meta_static(self, html: str) -> Dict[str, str]:
        """Extract meta information from static HTML."""
        parser = HTMLParser(html)
        meta = {
            "title": "",
            "description": "",
            "language": "en",
            "canonical": None
        }
        
        # Title
        title_tag = parser.css_first("title")
        if title_tag:
            meta["title"] = title_tag.text().strip()
        
        og_title = parser.css_first('meta[property="og:title"]')
        if og_title and og_title.attributes.get("content"):
            meta["title"] = og_title.attributes["content"]
        
        # Description
        desc_tag = parser.css_first('meta[name="description"]')
        if desc_tag and desc_tag.attributes.get("content"):
            meta["description"] = desc_tag.attributes["content"]
        
        og_desc = parser.css_first('meta[property="og:description"]')
        if og_desc and og_desc.attributes.get("content"):
            meta["description"] = og_desc.attributes["content"]
        
        # Language
        html_tag = parser.css_first("html")
        if html_tag and html_tag.attributes.get("lang"):
            meta["language"] = html_tag.attributes["lang"][:2]  # First 2 chars
        
        # Canonical
        canonical = parser.css_first('link[rel="canonical"]')
        if canonical and canonical.attributes.get("href"):
            meta["canonical"] = canonical.attributes["href"]
        
        return meta
    
    async def _extract_meta_js(self, page: Page) -> Dict[str, str]:
        """Extract meta information using Playwright."""
        meta = {
            "title": "",
            "description": "",
            "language": "en",
            "canonical": None
        }
        
        try:
            meta["title"] = await page.title() or ""
        except:
            pass
        
        try:
            desc = await page.get_attribute('meta[name="description"]', "content")
            if desc:
                meta["description"] = desc
        except:
            pass
        
        try:
            lang = await page.get_attribute("html", "lang")
            if lang:
                meta["language"] = lang[:2]
        except:
            pass
        
        try:
            canonical = await page.get_attribute('link[rel="canonical"]', "href")
            if canonical:
                meta["canonical"] = canonical
        except:
            pass
        
        return meta
    
    def _parse_sections(self, html: str, base_url: str) -> List[Dict[str, Any]]:
        """Parse HTML into sections."""
        if not html or not html.strip():
            # Return a minimal section if HTML is empty
            return [{
                "id": "empty-0",
                "type": "unknown",
                "label": "Empty Content",
                "sourceUrl": base_url,
                "content": {
                    "headings": [],
                    "text": "",
                    "links": [],
                    "images": [],
                    "lists": [],
                    "tables": []
                },
                "rawHtml": "",
                "truncated": False
            }]
        
        parser = HTMLParser(html)
        sections = []
        
        # Filter out noise
        noise_selectors = [
            '[class*="cookie"]',
            '[class*="banner"]',
            '[class*="modal"]',
            '[class*="popup"]',
            '[class*="overlay"]',
            '[id*="cookie"]',
            '[id*="banner"]',
            '[id*="modal"]',
            '[id*="popup"]'
        ]
        
        for selector in noise_selectors:
            for elem in parser.css(selector):
                elem.decompose()
        
        # Group by landmarks and headings
        section_elements = []
        
        # Find landmark elements
        landmarks = parser.css("header, nav, main, section, footer, article")
        for landmark in landmarks:
            section_elements.append(landmark)
        
        # If no landmarks, use headings to create sections
        if not section_elements:
            headings = parser.css("h1, h2, h3")
            for heading in headings:
                # Create a section from heading and following siblings
                section_elements.append(heading.parent)
        
        # If still no sections, use body as one section
        if not section_elements:
            body = parser.body
            if body:
                section_elements.append(body)
        
        # Process each section
        for idx, elem in enumerate(section_elements[:20]):  # Limit to 20 sections
            section = self._extract_section(elem, base_url, idx)
            if section:
                sections.append(section)
        
        # Ensure at least one section
        if not sections:
            body = parser.body
            if body:
                section = self._extract_section(body, base_url, 0)
                if section:
                    sections.append(section)
        
        return sections
    
    def _extract_section(self, elem, base_url: str, idx: int) -> Optional[Dict[str, Any]]:
        """Extract content from a section element."""
        if not elem:
            return None
        
        # Determine type and label
        tag_name = elem.tag.lower() if hasattr(elem, 'tag') else 'div'
        section_type = self._determine_type(tag_name, elem)
        label = self._derive_label(elem)
        
        # Extract content
        headings = []
        for h in elem.css("h1, h2, h3, h4, h5, h6"):
            heading_text = h.text().strip()
            if heading_text:
                headings.append(heading_text)
        
        # Text content
        text = elem.text().strip()
        # Clean up text (remove excessive whitespace)
        text = re.sub(r'\s+', ' ', text)
        
        # Links
        links = []
        for link in elem.css("a"):
            href = link.attributes.get("href", "")
            link_text = link.text().strip()
            if href:
                absolute_url = urljoin(base_url, href)
                links.append({"text": link_text, "href": absolute_url})
        
        # Images
        images = []
        for img in elem.css("img"):
            src = img.attributes.get("src", "")
            alt = img.attributes.get("alt", "")
            if src:
                absolute_url = urljoin(base_url, src)
                images.append({"src": absolute_url, "alt": alt})
        
        # Lists
        lists = []
        for ul_ol in elem.css("ul, ol"):
            list_items = []
            for li in ul_ol.css("li"):
                item_text = li.text().strip()
                if item_text:
                    list_items.append(item_text)
            if list_items:
                lists.append(list_items)
        
        # Tables
        tables = []
        for table in elem.css("table"):
            table_data = []
            for row in table.css("tr"):
                row_data = []
                for cell in row.css("td, th"):
                    cell_text = cell.text().strip()
                    row_data.append(cell_text)
                if row_data:
                    table_data.append(row_data)
            if table_data:
                tables.append(table_data)
        
        # Raw HTML (truncated)
        raw_html = str(elem.html) if hasattr(elem, 'html') else str(elem)
        truncated = False
        if len(raw_html) > 2000:
            raw_html = raw_html[:2000] + "..."
            truncated = True
        
        return {
            "id": f"{section_type}-{idx}",
            "type": section_type,
            "label": label,
            "sourceUrl": base_url,
            "content": {
                "headings": headings[:10],  # Limit headings
                "text": text[:5000] if len(text) > 5000 else text,  # Limit text
                "links": links[:50],  # Limit links
                "images": images[:20],  # Limit images
                "lists": lists[:10],  # Limit lists
                "tables": tables
            },
            "rawHtml": raw_html,
            "truncated": truncated
        }
    
    def _determine_type(self, tag_name: str, elem) -> str:
        """Determine section type."""
        tag_lower = tag_name.lower()
        class_attr = ""
        id_attr = ""
        
        if hasattr(elem, 'attributes'):
            class_attr = elem.attributes.get("class", "").lower()
            id_attr = elem.attributes.get("id", "").lower()
        
        if tag_lower == "header" or "header" in class_attr or "header" in id_attr:
            return "nav"
        elif tag_lower == "nav" or "nav" in class_attr or "nav" in id_attr:
            return "nav"
        elif tag_lower == "footer" or "footer" in class_attr or "footer" in id_attr:
            return "footer"
        elif tag_lower == "article":
            return "section"
        elif "hero" in class_attr or "hero" in id_attr or tag_lower == "section" and "hero" in (class_attr + id_attr):
            return "hero"
        elif "faq" in class_attr or "faq" in id_attr:
            return "faq"
        elif "pricing" in class_attr or "pricing" in id_attr:
            return "pricing"
        elif "grid" in class_attr or "grid" in id_attr:
            return "grid"
        elif "list" in class_attr or "list" in id_attr:
            return "list"
        else:
            return "section"
    
    def _derive_label(self, elem) -> str:
        """Derive a human-readable label for the section."""
        # Try to find a heading first
        for h in elem.css("h1, h2, h3"):
            label = h.text().strip()
            if label:
                return label[:50]  # Limit length
        
        # Fallback: use first 5-7 words of text
        text = elem.text().strip()
        words = text.split()[:7]
        if words:
            label = " ".join(words)
            return label[:50] if len(label) > 50 else label
        
        # Last resort
        tag_name = elem.tag.lower() if hasattr(elem, 'tag') else 'section'
        return tag_name.capitalize()


async def scrape_url(url: str) -> Dict[str, Any]:
    """Main entry point for scraping a URL."""
    async with Scraper() as scraper:
        result = await scraper.scrape(url)
        return result

