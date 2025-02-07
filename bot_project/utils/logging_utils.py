import logging

# Configure logging for the bot
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("var/bot.log"),  # Log to a file
        logging.StreamHandler()              # Also log to console
    ]
)

def get_logger(name: str):
    return logging.getLogger(name)
