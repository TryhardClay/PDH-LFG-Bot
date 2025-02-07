from utils.json_storage_utils import read_json_file, write_json_file

ACTIVE_LFG_FILE = "var/active_lfg_requests.json"

def load_active_lfg_requests():
    return read_json_file(ACTIVE_LFG_FILE).get("active_requests", [])

def save_active_lfg_request(request):
    data = read_json_file(ACTIVE_LFG_FILE)
    if "active_requests" not in data:
        data["active_requests"] = []
    data["active_requests"].append(request)
    write_json_file(ACTIVE_LFG_FILE, data)

def remove_lfg_request(request_id):
    data = read_json_file(ACTIVE_LFG_FILE)
    if "active_requests" in data:
        data["active_requests"] = [req for req in data["active_requests"] if req["id"] != request_id]
        write_json_file(ACTIVE_LFG_FILE, data)
