import asyncio
import json
import logging

import aiohttp
from aiohttp_retry import ExponentialRetry, RetryClient

# ... other imports and constants

logger = logging.getLogger(__name__)

async def create_spelltable_game(game_type, player_count, auth_key, **kwargs):
    """Creates a SpellTable game using the API."""

    api_endpoint = "https://xerb3yhfde.execute-api.us-west-2.amazonaws.com/prod/createGame"
    headers = {
        "Content-Type": "application/json",
        "key": auth_key,  # Use the auth key for authentication
        "User-Agent": "MySpellBot/1.0"  # Replace with your bot's name and version
    }
    payload = {
        "gameType": game_type,
        "playerCount": player_count,
        # ... other parameters as needed
    }

    try:
        async with RetryClient(
            raise_for_status=True,  # Raise HTTP errors for retry
            retry_options=ExponentialRetry(attempts=5),
        ) as client:
            async with client.post(api_endpoint, headers=headers, json=payload) as resp:
                raw_data = await resp.read()
                data = json.loads(raw_data)
                if not data or "gameUrl" not in data:
                    logger.warning(
                        "warning: gameUrl missing from SpellTable API response (%s): %s",
                        resp.status,
                        data,
                    )
                    return None
                returned_url = str(data["gameUrl"])
                return returned_url.replace(
                    "www.spelltable.com",
                    "spelltable.wizards.com",
                )

    except aiohttp.ClientError as ex:
        # More specific exception handling for client errors
        logger.warning(
            "warning: SpellTable API client error: %s, data: %s, raw: %s",
            ex,
            data,
            raw_data,
            exc_info=True,  # Include exception traceback in logs
        )
        return None

    except Exception as ex:
        # Catch-all exception handling for unexpected errors
        if raw_data == b"upstream request timeout":
            return None
        logger.exception("error: unexpected exception: data: %s, raw: %s", data, raw_data)
        return None
