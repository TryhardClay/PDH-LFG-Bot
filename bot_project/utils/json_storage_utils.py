import json
from typing import Any

def read_json_file(file_path: str) -> Any:
    try:
        with open(file_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON in {file_path}: {e}")
        return {}

def write_json_file(file_path: str, data: Any) -> None:
    with open(file_path, "w") as file:
        json.dump(data, file, indent=4)
