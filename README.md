# PDH-LFG-Bot
# Cross-Server Communication Bot

This Discord bot facilitates communication and coordination between different servers by relaying messages, prompts, and other content between designated channels. It's particularly useful for communities that want to collaborate or share information across servers, such as gaming groups, hobbyist clubs, or online communities.

## Features

* **Cross-server message relaying:** Relays messages, including text, embeds, and attachments, between connected channels in different servers.
* **Filtering:** Allows administrators to assign filters (e.g., "casual" or "cpdh") to channels, ensuring that messages are only relayed between channels with matching filters.
* **SpellBot prompt redistribution:** Captures `/lfg` prompts from SpellBot (a bot for organizing SpellTable games) and redistributes them to connected channels, helping players find games across servers.
* **Slash commands:** Provides user-friendly slash commands for managing the bot's functionality:
    *   `/setchannel`: Sets a channel for cross-server communication and assigns a filter.
    *   `/disconnect`: Disconnects a channel from cross-server communication.
    *   `/listconnections`: Lists all connected channels and their filters.
    *   `/resetconfig`: Reloads the bot's configuration (for debugging/development).
    *   `/about`: Shows information about the bot and its commands.
* **Role management:** Creates and manages a role for the bot in each server it joins.
* **Error handling and logging:** Includes robust error handling and logging to ensure smooth operation and easy debugging.

## How to Use

1.  **Invite the bot to your server:** Use the following URL to invite the bot to your server:
    (Replace `YOUR_BOT_ID` with your bot's actual client ID)
    ```
    [invalid URL removed]
    ```
2.  **Grant necessary permissions:** Ensure the bot has the following permissions:
    *   "Manage Channels"
    *   "Manage Webhooks"
    *   "Manage Roles" (optional, for role creation)
3.  **Use the `/setchannel` command:** In each server, use the `/setchannel` command in a text channel to designate it for cross-server communication and assign a filter (e.g., "casual" or "cpdh").
4.  **Connect channels:** Repeat step 3 in other servers, ensuring that channels with matching filters are connected.
5.  **Start communicating:** Send messages in the connected channels, and the bot will relay them to the corresponding channels in other servers.

## Additional Notes

*   The bot uses webhooks to relay messages between servers.
*   The bot stores its configuration in a `webhooks.json` file.
*   The bot creates a role with its own name in each server it joins (optional).
*   The bot can be reloaded using the `/resetconfig` command.

## Disclaimer

This bot is still under development and might have limitations or bugs. Please use it responsibly and report any issues you encounter.

---------------------------
###Additional Future Functionality

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
