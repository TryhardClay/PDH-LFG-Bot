import os
import requests
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Retrieve token from environment variable
token = os.getenv("TOKEN")
if not token:
    logging.error("Discord bot token not found in environment variables.")
    exit()

# Define API endpoint
url = "https://discord.com/api/v10/users/@me"
headers = {
    "Authorization": f"Bot {token}"
}

try:
    # Send GET request to Discord API
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        logging.info("Bot token is valid. Successfully connected to Discord.")
        logging.info(f"Bot details: {response.json()}")
    elif response.status_code == 401:
        logging.error("Unauthorized. The token is invalid or has been revoked.")
    else:
        logging.error(f"Failed to connect to Discord. Status code: {response.status_code}, Response: {response.text}")

except requests.exceptions.RequestException as e:
    logging.error(f"An error occurred while connecting to Discord: {e}")
