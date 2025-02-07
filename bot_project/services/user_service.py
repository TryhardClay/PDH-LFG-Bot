from utils.json_storage_utils import read_json_file, write_json_file

BANNED_USERS_FILE = "var/banned_users.json"
TRUSTED_ADMINS_FILE = "var/trusted_admins.json"

def is_user_banned(user_id: int) -> bool:
    data = read_json_file(BANNED_USERS_FILE)
    return user_id in data.get("banned_users", [])

def ban_user(user_id: int) -> None:
    if not is_user_trusted(user_id):
        data = read_json_file(BANNED_USERS_FILE)
        if "banned_users" not in data:
            data["banned_users"] = []
        if user_id not in data["banned_users"]:
            data["banned_users"].append(user_id)
            write_json_file(BANNED_USERS_FILE, data)

def unban_user(user_id: int) -> None:
    data = read_json_file(BANNED_USERS_FILE)
    if "banned_users" in data and user_id in data["banned_users"]:
        data["banned_users"].remove(user_id)
        write_json_file(BANNED_USERS_FILE, data)

def is_user_trusted(user_id: int) -> bool:
    trusted_admins = read_json_file(TRUSTED_ADMINS_FILE).get("trusted_admins", [])
    return user_id in trusted_admins
