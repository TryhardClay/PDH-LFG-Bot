import json
from typing import Any
from aiohttp.client_exceptions import ClientError
from utils.retry_utils import fetch_with_retries
from utils.logging_utils import get_logger
from config.settings import settings

logger = get_logger(__name__)

async def generate_tablestream_link(game: dict[str, Any]) -> tuple[str | None, str | None]:
    headers = {
        "user-agent": "bot/1.0",
        "Authorization": f"Bearer: {settings.TABLESTREAM_AUTH_KEY}",
    }

    ts_args = {
        "roomName": f"Game{game['id']}",
        "gameType": game.get("format", "MTGCommander"),
        "maxPlayers": game.get("players", 4),
        "private": True,
        "initialScheduleTTLInSeconds": settings.TABLESTREAM_TIMEOUT_SECONDS,
    }

    try:
        response = await fetch_with_retries(
            settings.TABLESTREAM_CREATE,
            headers=headers,
            json_data=ts_args,
        )
        room = response.get("room", {})
        return room.get("roomUrl"), room.get("password")

    except ClientError as ex:
        logger.warning(f"TableStream API failure: {ex}")
        return None, None
    except Exception as ex:
        logger.error(f"Unexpected error: {ex}")
        return None, None
