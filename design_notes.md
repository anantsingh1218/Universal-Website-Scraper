# Design Notes

## Static vs JS Fallback

**Strategy**: The scraper uses a static-first approach with intelligent fallback to JS rendering.

1. **Initial Static Scrape**: Always attempts static scraping first using `httpx` for speed and efficiency.

2. **Fallback Heuristic**: Falls back to Playwright JS rendering if:
   - The page has less than 200 characters of text content, OR
   - No substantial main content sections are detected (no `<main>`, `<article>` with >100 chars)

3. **Interaction Requirement**: Even if static scraping succeeds, the scraper still uses Playwright for interaction flows (clicks, scrolls, pagination) to ensure depth ≥ 3.

This approach balances speed (static is faster) with completeness (JS ensures dynamic content is captured).

## Wait Strategy for JS

- [x] Network idle
- [x] Fixed sleep
- [ ] Wait for selectors

**Details**: 
- Primary wait strategy uses `wait_until="networkidle"` in Playwright, which waits for network activity to settle
- Additional fixed sleep of 2 seconds after navigation to allow JavaScript to fully render dynamic content
- After each interaction (click, scroll), a 1-2 second sleep ensures content loads
- Timeout set to 30 seconds for page loads to prevent indefinite hanging

## Click & Scroll Strategy

**Click flows implemented**:
- **Tabs**: Searches for elements with `[role="tab"]`, `.tab`, or `[data-tab]` attributes. Clicks up to 3 tabs.
- **Load More buttons**: Attempts multiple selectors:
  - `button:has-text("Load more")`
  - `button:has-text("Show more")`
  - `[class*="load-more"]`
  - `[class*="show-more"]`
- Stops after first successful click to avoid excessive interactions

**Scroll / pagination approach**:
- Performs 3 scroll operations, scrolling to the bottom of the page each time
- After each scroll, checks for pagination links (`a:has-text("Next")`, `[rel="next"]`)
- If pagination link found and depth < 3, navigates to next page
- Tracks all visited URLs in `interactions.pages`

**Stop conditions**:
- Maximum depth of 3 pages/scrolls (as per requirement)
- 30-second timeout per page load
- Maximum 3 tab clicks to avoid excessive interaction

## Section Grouping & Labels

**How you group DOM into sections**:
1. **Primary**: Uses HTML5 semantic landmarks (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`, `<article>`)
2. **Secondary**: If no landmarks found, groups content by headings (`<h1>`, `<h2>`, `<h3>`) and their parent containers
3. **Fallback**: If no clear sections, uses `<body>` as a single section
4. Limits to 20 sections per page to prevent excessive output

**How you derive section `type` and `label`**:
- **Type determination**:
  - Checks HTML tag name (`header` → `nav`, `footer` → `footer`, etc.)
  - Examines `class` and `id` attributes for keywords:
    - `hero` → `hero`
    - `faq` → `faq`
    - `pricing` → `pricing`
    - `grid` → `grid`
    - `list` → `list`
  - Defaults to `section` if no match
- **Label derivation**:
  1. First attempts to find the first `<h1>`, `<h2>`, or `<h3>` within the section
  2. If no heading found, uses first 5-7 words of the section's text content
  3. Truncates to 50 characters maximum
  4. Last resort: uses tag name capitalized

## Noise Filtering & Truncation

**What you filter out**:
- Cookie banners: `[class*="cookie"]`, `[id*="cookie"]`
- Banners: `[class*="banner"]`, `[id*="banner"]`
- Modals: `[class*="modal"]`, `[id*="modal"]`
- Popups: `[class*="popup"]`, `[id*="popup"]`
- Overlays: `[class*="overlay"]`

These elements are removed from the DOM before section parsing using `decompose()`.

**How you truncate `rawHtml` and set `truncated`**:
- `rawHtml` is limited to 2000 characters
- If HTML exceeds 2000 chars, it's truncated and `"..."` is appended
- `truncated` boolean is set to `true` if truncation occurred, `false` otherwise
- This prevents excessive JSON payload size while preserving enough HTML for inspection

## Additional Design Decisions

1. **Absolute URLs**: All links and images are converted to absolute URLs using `urljoin()` to ensure they're usable regardless of context.

2. **Content Limits**: To prevent memory issues:
   - Headings: max 10 per section
   - Text: max 5000 characters per section
   - Links: max 50 per section
   - Images: max 20 per section
   - Lists: max 10 per section

3. **Error Recovery**: The scraper attempts to return partial results even when errors occur, populating the `errors` array rather than failing completely.

4. **Browser Management**: Uses context manager pattern to ensure browser resources are properly cleaned up, even on errors.

5. **URL Validation**: Only accepts `http://` and `https://` URLs, rejecting other schemes with a clear error message.

