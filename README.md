# PDH-LFG-Bot
## Cross-Server Communication and LFG Bot for Discord

The **PDH-LFG Bot** is designed to provide dynamic, cross-server communication and matchmaking for Magic: The Gathering players and other communities. It relays messages, manages game requests, and automates TableStream game room creation, making it the perfect tool for creating interactive, community-driven experiences across multiple Discord servers.

---

## **Features**

### **Message Relaying and Synchronization**
- **Cross-server message relaying:** Dynamically relays messages, embeds, and prompts between connected channels in different servers.
- **Attribution:** Relayed messages retain the original sender’s name and avatar, ensuring context is maintained across servers.
- **Message ID Tracking:** Assigns a globally consistent ID to each message for seamless synchronization and updates across servers.
- **Edits and deletions:** Message edits and deletions are propagated across all servers in real-time, ensuring consistency.

### **Advanced Reaction Management**
- Users can react to any message in connected channels, and their reactions are mirrored across all corresponding copies in other servers.

### **Interactive LFG Embeds**
- **/biglfg Command:** Creates dynamic, interactive LFG (Looking For Group) embeds.
  - Displays available slots and automatically updates as players join or leave.
  - Switches to "Your game is ready!" when 4 players are confirmed, with automatic TableStream game creation.
  - Includes a 20-minute timeout feature with visual updates.
  - Players receive DMs with game details, including links to join the TableStream game or provide a Spelltable link.

### **TableStream Integration**
- Automatically creates and links TableStream game rooms when the player count requirement is met.
- Provides game passwords (if required) and links via private DMs to players.

### **Admin and Restricted Commands**
#### **Admin Commands:**
- **/setchannel (admin):** Assigns a channel for cross-server communication and sets a filter (e.g., casual or cpdh).
- **/disconnect (admin):** Removes a channel from the communication network.
- **/updateconfig (admin):** Reloads configurations and syncs the command tree without restarting the bot.
- **/listconnections (admin):** Lists active channel connections and their filters.

#### **Restricted Commands (Super Admins Only):**
- **/banuser (restricted):** Temporarily or permanently bans a user from interacting with bot-controlled channels and commands.
- **/unbanuser (restricted):** Unbans a previously banned user.
- **/listbans (restricted):** Displays a list of currently banned users, their ban duration, and the reason for the ban.
- **/listadmins (restricted):** Lists all trusted administrators with special access to restricted commands.

### **Slash Commands for Players:**
- **/biglfg:** Create a cross-server LFG request and manage players dynamically.
- **/gamerequest:** Generate a TableStream game room manually.
- **/about:** Display details about the bot, available commands, and rules for use.

---

## **Installation Instructions**
### **(For Server Admins Only)**

1. **Invite the Bot:** [Click here to invite the bot](<[INSERT_BOT_INVITE_URL](https://discord.com/oauth2/authorize?client_id=1314984669485334528&permissions=1102464805986&integration_type=0&scope=bot+applications.commands)>) to your server.
2. **Set Up Permissions:** Grant the bot the following permissions to ensure it works correctly:
   - Send Messages
   - Read Messages
   - Manage Webhooks
   - Manage Roles (Mandatory for Moderation Purposes)
3. **Set a Channel:** Create a dedicated channel for the bot and assign it using the **/setchannel** command.
4. **Assign Filters:** Ensure channels in different servers have matching filters (e.g., casual or cpdh) to connect them.
5. **Start Using the Bot:** Once configured, the bot will begin relaying messages and managing LFG requests.

---

## **How to Use the Bot**

1. **Relaying Messages:** Send messages in designated channels, and the bot will relay them to connected servers with matching filters.
2. **Organizing Games:** Use the **/biglfg** command to create an LFG request across servers.
3. **Automatic Game Room Creation:** Once enough players join the LFG, a TableStream game room is created automatically.
4. **Bans and Admin Management:** Super admins can manage bans using **/banuser**, **/unbanuser**, and **/listbans** commands.

---

## **Technology Stack**
- **Gateways:** Discord’s Gateway API is used for all message delivery, updates, reactions, and edits.
- **Webhooks:** Limited to channel setup and filter management.
- **TTL Caching:** Manages temporary message metadata with expiration for performance optimization.

---

## **Disclaimer**
This bot is actively maintained and updated. However, as with any ongoing development, there may be bugs or limitations. Please report any issues.

---

## **Contributing**
We welcome contributions to enhance the bot. Fork the repository and submit a pull request to share improvements.

---

## **License**
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

