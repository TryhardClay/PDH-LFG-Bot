# utils.py
import asyncio
import logging

import aiohttp

logger = logging.getLogger(__name__)


async def fetch_webpage(url, retry_attempts=5):
    """Fetches the content of a webpage with retry attempts."""

    async with aiohttp.ClientSession() as session:
        for attempt in range(retry_attempts):
            try:
                async with session.get(url, headers={'User-Agent': 'Mozilla/5.0'}) as response:  # Added User-Agent
                    response.raise_for_status()  # Raise an exception for bad status codes
                    return await response.text()
            except aiohttp.ClientError as e:
                logger.warning(
                    "Attempt %d/%d failed to fetch %s: %s",
                    attempt + 1,
                    retry_attempts,
                    url,
                    e,
                )
                if attempt < retry_attempts - 1:  # Don't sleep on the last attempt
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise  # Re-raise the exception after all attempts fail


async def parse_html(html_content):
    """Parses HTML content using BeautifulSoup (example)."""

    from bs4 import BeautifulSoup  # Import BeautifulSoup locally

    soup = BeautifulSoup(html_content, "html.parser")
    # ... (your HTML parsing logic here)
    return ...  # Return parsed data

# ... (other utility functions)
