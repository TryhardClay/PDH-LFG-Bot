import os

class Settings:
    # API Keys (fetched from environment variables)
    TABLESTREAM_AUTH_KEY = os.getenv("TABLESTREAM_AUTH_KEY", "default_tablestream_key")
    SPELLTABLE_AUTH_KEY = os.getenv("SPELLTABLE_AUTH_KEY", "default_spelltabel_key")
    
    # External URLs
    TABLESTREAM_CREATE = os.getenv("TABLESTREAM_CREATE_URL", "https://api.tablestream.com/create")

    # Retry and timeout settings
    TABLESTREAM_RETRY_ATTEMPTS = int(os.getenv("TABLESTREAM_RETRY_ATTEMPTS", 5))
    TABLESTREAM_TIMEOUT_SECONDS = int(os.getenv("TABLESTREAM_TIMEOUT_SECONDS", 3600))  # 1 hour
    
    # Discord token
    DISCORD_BOT_TOKEN = os.getenv("TOKEN")

    # Other bot-related configuration
    BOT_PREFIX = os.getenv("BOT_PREFIX", "/")  # Slash commands as default

settings = Settings()
