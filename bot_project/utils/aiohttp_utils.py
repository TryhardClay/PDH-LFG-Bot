from aiohttp import ClientSession

async def create_aiohttp_session():
    return ClientSession()

async def close_aiohttp_session(session: ClientSession):
    if not session.closed:
        await session.close()
