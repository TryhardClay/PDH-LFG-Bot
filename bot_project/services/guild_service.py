from utils.json_storage_utils import read_json_file, write_json_file

BANNED_SERVERS_FILE = "var/banned_users.json"

def is_server_banned(guild_id: int) -> bool:
    data = read_json_file(BANNED_SERVERS_FILE)
    return guild_id in data.get("banned_servers", [])

def ban_server(guild_id: int) -> None:
    data = read_json_file(BANNED_SERVERS_FILE)
    if "banned_servers" not in data:
        data["banned_servers"] = []
    if guild_id not in data["banned_servers"]:
        data["banned_servers"].append(guild_id)
        write_json_file(BANNED_SERVERS_FILE, data)

def unban_server(guild_id: int) -> None:
    data = read_json_file(BANNED_SERVERS_FILE)
    if "banned_servers" in data and guild_id in data["banned_servers"]:
        data["banned_servers"].remove(guild_id)
        write_json_file(BANNED_SERVERS_FILE, data)
