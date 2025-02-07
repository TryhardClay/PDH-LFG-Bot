from aiohttp import ClientSession
from aiohttp_retry import RetryClient, ExponentialRetry

def get_retry_client(retries=5, base_delay=1, max_delay=16):
    retry_options = ExponentialRetry(attempts=retries, start_timeout=base_delay, max_timeout=max_delay)
    return RetryClient(raise_for_status=False, retry_options=retry_options)

async def fetch_with_retries(url, headers=None, json_data=None):
    async with get_retry_client() as client:
        async with client.post(url, headers=headers, json=json_data) as response:
            return await response.json()
