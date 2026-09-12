import os
import asyncio
import json
from typing import List, Optional, Dict, Set
import logging
from collections import deque

from groq import AsyncGroq
import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

try:
    from config import GROQ_API_KEY
except ImportError:
    GROQ_API_KEY = ""

DEFAULT_MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """
you are FishR, an Discord Economy bot with a silly personality

you must follow these rules:
- all of your responses are always lowercase
- you sometime use aberrations whenever you want to
## Example
- idk = i don't know
- idc = i don't care
- alr = alright
- ok = okay
- ngl = not gonna lie

if someone asks for your source code, you will respond with https://github.com/Ramimnur20/fishr
if someone asks for your owner, you will respond with "voby7"
if someone asks for your commands, you will tell the user to use .help to see all commands

always make your responses only around 20 - 30 words, 40 AT MAX
SOMETIMES encourage the user to try fishing via .fish command
"""

# ==================== Conversation Context Management ====================

MAX_CONTEXT_MESSAGES = 10


class ConversationContext:
    """Manages conversation context per channel."""

    def __init__(self):
        self._contexts: Dict[int, deque] = {}
        self._locks: Dict[int, asyncio.Lock] = {}

    def _get_lock(self, channel_id: int) -> asyncio.Lock:
        if channel_id not in self._locks:
            self._locks[channel_id] = asyncio.Lock()
        return self._locks[channel_id]

    async def add_message(self, channel_id: int, role: str, content: str, username: str = None):
        """Add a message to context."""
        async with self._get_lock(channel_id):
            if channel_id not in self._contexts:
                self._contexts[channel_id] = deque(maxlen=MAX_CONTEXT_MESSAGES)

            msg = {"role": role, "content": content}
            if username:
                msg["name"] = username

            self._contexts[channel_id].append(msg)

    async def get_context(self, channel_id: int) -> List[dict]:
        """Get formatted context for AI."""
        async with self._get_lock(channel_id):
            return list(self._contexts.get(channel_id, []))

    async def clear_context(self, channel_id: int):
        """Clear context for a channel."""
        async with self._get_lock(channel_id):
            self._contexts.pop(channel_id, None)


# Global context instance
context = ConversationContext()

# ==================== User Tracking ====================

USERS_FILE = "data/known_users.json"
_known_users: Set[str] = set()
_users_file_lock = asyncio.Lock()


def _load_known_users() -> Set[str]:
    """Load known users from JSON file."""
    try:
        with open(USERS_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("usernames", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_known_users(users: Set[str]):
    """Save known users to JSON file."""
    os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
    with open(USERS_FILE, "w") as f:
        json.dump({"usernames": list(users)}, f, indent=2)


async def track_user(username: str) -> bool:
    """
    Track a username if new. Returns True if newly discovered.
    """
    if not username:
        return False

    async with _users_file_lock:
        if username in _known_users:
            return False

        _known_users.add(username)
        _save_known_users(_known_users)
        logger.info(f"New user tracked: {username}")
        return True


def get_known_users() -> List[str]:
    """Get list of known usernames."""
    return list(_known_users)


# Load known users at startup
_known_users = _load_known_users()


# ==================== Web Search (DuckDuckGo) ====================

async def search_duckduckgo(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """
    Search DuckDuckGo for the given query and return top results.
    Returns list with title, url, and snippet for each result.
    """
    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(
            None, 
            lambda: _ddgs_search(query, max_results)
        )
        return results
    except Exception as e:
        logger.error(f"DuckDuckGo search error: {e}")
        return []


def _ddgs_search(query: str, max_results: int) -> List[Dict[str, str]]:
    """Synchronous DuckDuckGo search helper."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo_search not installed")
        return []
    
    results = []
    with DDGS() as ddgs:
        for result in ddgs.text(query, max_results=max_results):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("href", ""),
                "snippet": result.get("body", "")
            })
    return results


async def search_web(query: str, max_results: int = 3) -> List[Dict[str, str]]:
    """Search DuckDuckGo for current information."""
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        logger.error("duckduckgo_search not installed")
        return []

    try:
        results = []
        with DDGS() as ddgs:
            for result in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "body": result.get("body", ""),
                    "href": result.get("href", "")
                })
        return results
    except Exception as e:
        logger.error(f"Search error: {e}")
        return []


# ==================== Page Fetcher (Safe Reader) ====================

async def fetch_page(url: str, timeout: float = 8.0, max_size: int = 2 * 1024 * 1024) -> Optional[str]:
    """
    Fetch a single URL and return the HTML content safely.
    - timeout: Request timeout in seconds (default 8)
    - max_size: Maximum response size in bytes (default 2MB)
    Returns raw HTML text or None if blocked/error.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }

    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                if response.status != 200:
                    return None

                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) > max_size:
                    return None

                content = await response.text()
                if len(content.encode('utf-8')) > max_size:
                    return None

                return content
    except asyncio.TimeoutError:
        return None
    except aiohttp.ClientError:
        return None
    except Exception:
        return None


# ==================== HTML Cleaning ====================

def extract_text(html: str) -> str:
    """
    Extract clean readable text from HTML.
    Strips scripts, styles, nav, footer.
    Prioritizes main, article, headings (h1-h3), paragraphs.
    """
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return ""

    # Remove script, style, nav, footer, header, aside, svg, canvas
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "svg", "canvas"]):
        tag.decompose()

    # Prioritize main or article
    content = None
    for selector in ["main", "article"]:
        content = soup.find(selector)
        if content:
            break

    if not content:
        content = soup.find("body") or soup

    text_parts = []

    # Get headings first
    for heading in content.find_all(["h1", "h2", "h3"]):
        text = heading.get_text(strip=True)
        if text:
            text_parts.append(text)

    # Get paragraphs
    for p in content.find_all("p"):
        text = p.get_text(strip=True)
        if text:
            text_parts.append(text)

    # Get other meaningful elements
    for elem in content.find_all(["li", "span", "div"]):
        text = elem.get_text(strip=True)
        if text and len(text) > 20:
            text_parts.append(text)

    # Join and clean
    text = "\n\n".join(text_parts)
    lines = [line.strip() for line in text.split("\n")]
    text = "\n".join(line for line in lines if line)

    return text[:10000]


# ==================== Web AI Integration ====================

async def fetch_and_clean_pages(urls: List[str], max_pages: int = 3) -> List[Dict[str, str]]:
    """Fetch multiple URLs concurrently and extract clean text."""
    pages = []
    semaphore = asyncio.Semaphore(3)

    async def fetch_one(url: str) -> Optional[Dict[str, str]]:
        async with semaphore:
            html = await fetch_page(url)
            if html:
                content = extract_text(html)
                if content:
                    title = url.split("//")[-1].split("/")[0]
                    return {"title": title, "url": url, "content": content}
            return None

    tasks = [fetch_one(url) for url in urls[:max_pages]]
    results = await asyncio.gather(*tasks)
    
    for result in results:
        if result:
            pages.append(result)

    return pages


def build_context(pages: List[Dict[str, str]], max_chars: int = 4000) -> str:
    """Compress multiple pages into AI context."""
    parts = []
    
    for page in pages:
        part = f"Source: {page['title']} ({page['url']})\n{page['content'][:1200]}"
        parts.append(part)
    
    context = "\n\n---\n\n".join(parts)
    return context[:max_chars]


async def web_ai_query(query: str, max_results: int = 3) -> Optional[str]:
    """Full pipeline: search, fetch, clean, return context."""
    results = await search_duckduckgo(query, max_results)
    
    if not results:
        return None

    urls = [r["url"] for r in results if r.get("url")]
    content = await fetch_and_clean_pages(urls, max_pages=max_results)
    
    if not content:
        return None

    return build_context(content)


# ==================== Enhanced Web Integration ====================

def needs_search(query: str) -> bool:
    """Detect if a query needs web search."""
    search_keywords = [
        "who", "what", "when", "where", "why", "how",
        "latest", "recent", "today", "now", "current", "news",
        "winner", "won", "update", "happened", "2024", "2025", "2026"
    ]
    
    query_lower = query.lower()
    return any(kw in query_lower for kw in search_keywords)


async def get_web_enhanced_response(query: str, messages: List[dict], system_prompt: str = None) -> Optional[str]:
    """
    Get AI response with web search context if needed.
    Uses web search, fetches pages, and includes clean content in the prompt.
    """
    if not needs_search(query):
        return None

    web_context = await web_ai_query(query, max_results=3)
    if web_context:
        web_message = {
            "role": "system",
            "content": f"Web search results:\n{web_context}\n\nSummarize briefly in 1-2 sentences."
        }
        messages = [web_message] + messages

    return await get_ai_response(messages, system_prompt=system_prompt)


# ==================== AI Response Generation ====================

async def get_ai_response(messages: List[dict], model: str = DEFAULT_MODEL, system_prompt: str = None) -> Optional[str]:
    """Get AI response from Groq API."""
    api_key = GROQ_API_KEY or os.getenv("GROQ_API_KEY", "")
    if not api_key:
        logger.error("Groq API key missing")
        return "idk broke rn"

    try:
        async_client = AsyncGroq(api_key=api_key)
        
        prompt = system_prompt if system_prompt else SYSTEM_PROMPT
        full_messages = [{"role": "system", "content": prompt}] + messages

        completion = await async_client.chat.completions.create(
            model=model,
            messages=full_messages,
            temperature=1,
            max_tokens=100,
            top_p=1,
            stream=False,
        )

        return completion.choices[0].message.content

    except Exception as e:
        logger.error(f"Groq API error: {e}")
        return "idk broke rn"