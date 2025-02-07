from discord import TextChannel, VoiceChannel
from utils.json_storage_utils import read_json_file, write_json_file

WEBHOOK_DATA_FILE = "var/webhook_data.json"

def get_channel_webhook_data(channel_id: int) -> dict:
    data = read_json_file(WEBHOOK_DATA_FILE)
    return data.get(str(channel_id), {})

def save_channel_webhook(channel_id: int, webhook_url: str) -> None:
    data = read_json_file(WEBHOOK_DATA_FILE)
    data[str(channel_id)] = {"webhook_url": webhook_url}
    write_json_file(WEBHOOK_DATA_FILE, data)

def remove_channel_webhook(channel_id: int) -> None:
    data = read_json_file(WEBHOOK_DATA_FILE)
    if str(channel_id) in data:
        del data[str(channel_id)]
        write_json_file(WEBHOOK_DATA_FILE, data)
