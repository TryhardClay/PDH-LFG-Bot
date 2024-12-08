# PDH-LFG-Bot
A cross server LFG bot

---------------------------
#Additional functionality

## LFG Bot

This bot is designed to create SpellTable game links using the (undocumented) SpellTable API. It's inspired by the functionality of SpellBot (https://github.com/lexicalunit/spellbot) but aims to be a simpler implementation focusing on game creation.

## Functionality

The bot currently supports the following:

* **`/lfg` command:** This slash command allows users to create SpellTable game links directly within Discord. It takes two arguments:
    * `game_type`: The type of game (e.g., "Commander", "Standard").
    * `player_count`: The number of players.

## Code Overview

The bot's code is organized into three main files:

* **`lfgbot.py`:**
    * Contains the `create_spelltable_game` function, which interacts with the SpellTable API to create games.
    * Handles authentication using a `SPELLTABLE_AUTH_KEY`.
    * Includes error handling and retry logic for robust API interaction.
* **`client.py`:**
    * Sets up the Discord bot and handles the `/lfg` slash command.
    * Retrieves the `SPELLTABLE_AUTH_KEY` from the bot's settings.
    * Sends requests to the `create_spelltable_game` function and sends the resulting game link (or error message) to the user.
* **`utils.py`:**
    * Contains utility functions for fetching web pages and parsing HTML content.
    * Includes a `fetch_webpage` function with retry logic for handling network errors.
    * Provides a `parse_html` function (currently with placeholder logic) for parsing HTML content.

## Remaining Unknown Items (Further Research)

* **`SPELLTABLE_AUTH_KEY` acquisition:** The code assumes the existence of a `SPELLTABLE_AUTH_KEY`. Further research is needed to determine how to obtain this key. Possible avenues include:
    * Examining the SpellTable website or documentation for clues.
    * Contacting SpellTable or Wizards of the Coast for developer information.
    * Reverse-engineering the SpellTable website or SpellBot's code to understand how the key is obtained and used.
* **Full API capabilities:** The bot currently only uses the `/createGame` endpoint. Further research could explore other potential endpoints or functionalities of the SpellTable API.
* **HTML parsing:** The `parse_html` function in `utils.py` has placeholder logic. If you need to extract additional information from SpellTable web pages (e.g., game status, player details), you'll need to implement the necessary HTML parsing logic.
* **Additional features:**  Consider adding more features to enhance the bot's functionality, such as:
    * Game listing management:  Allow users to list and join existing games.
    * Player management:  Enable users to add or remove players from games.
    * Discord integration:  Send game reminders, notifications, or updates to Discord channels.
    * User verification:  Implement a system to verify users and prevent abuse.

## Contributing

Contributions are welcome! If you'd like to contribute to this project, please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
