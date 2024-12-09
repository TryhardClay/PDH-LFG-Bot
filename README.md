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

## Contributing

Contributions are welcome! If you'd like to contribute to this project, please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
