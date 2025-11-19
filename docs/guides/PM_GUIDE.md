# CyTube Bot Control Guide - Using Private Messages

## Quick Start

You can control the bot by sending it private messages (PMs) with commands. This is easier than using the telnet shell and works from anywhere in the channel!

---

## Who Can Use Bot Commands?

⚠️ **IMPORTANT:** Only **moderators** (rank 2.0 or higher) can control the bot via PM.

- ❌ **Regular users** - No access to bot commands
- ❌ **Guests** - No access to bot commands  
- ✅ **Moderators** (rank 2.0+) - Full access to bot commands
- ✅ **Channel Admins** (rank 3.0+) - Full access to bot commands
- ✅ **Site Admins** (rank 255) - Full access to bot commands

If you try to send commands and the bot doesn't respond, check your rank with a channel admin.

---

## How to Send Commands

1. Click on the bot's username in the user list
2. Select "Private Message" 
3. Type your command in the PM window
4. Press Enter

**Example:**
```
help
```

The bot will respond with the results in the PM window.

---

## Available Commands

### 📊 Information Commands

#### `help`
Shows the list of all available commands.

**Example:**
```
help
```

#### `info`
Shows information about the bot and channel, including:
- Bot name and rank
- Channel name
- Number of users in chat and total viewers (includes those watching but not in chat)
- Playlist size and total duration
- Currently playing video

**Example:**
```
info
```

**Sample Output:**
```
Bot: MyBot
Rank: 3.0
AFK: No
Channel: mychannel
Users: 12 in chat, 25 connected
Playlist: 25 items
Duration: 3h 42m 15s
Now playing: Cool Video Title
```

#### `status`
Shows connection status and uptime information:
- How long the bot has been running
- Connection status and duration
- Current channel and playback state

**Example:**
```
status
```

**Sample Output:**
```
Uptime: 2h 15m 30s
Connected: Yes
Server: wss://cytu.be:443/socket.io/
Conn time: 1h 45m 20s
Channel: mychannel
Playback: Playing
```

#### `stats`
Shows database statistics including:
- Current users in chat vs. total viewers
- Peak number of users in chat (high water mark)
- Total unique users seen
- Top 5 most active chatters

**Example:**
```
stats
```

**Sample Output:**
```
Current: 12 in chat, 25 connected
Peak (chat): 35 (2025-11-07 14:30)
Peak (connected): 42 (2025-11-08 19:15)
Total seen: 156

Top chatters:
  1. Alice: 1234 msg
  2. Bob: 892 msg
  3. Charlie: 654 msg
```

---

### 👥 User Commands

#### `users`
Lists all users currently in the channel with their ranks. Also shows special flags like AFK, MUTED, or LEADER.

**Example:**
```
users
```

**Sample Output:**
```
Users in channel (5):
  [3.0] Admin
  [2.0] Moderator [LEADER]
  [1.0] RegularUser
  [0.0] Guest [AFK]
  [0.0] AnotherGuest
```

#### `user <username>`
Shows detailed information about a specific user, including:
- Username and rank
- AFK and muted status
- Total chat messages sent
- Total time connected

**Example:**
```
user Alice
```

**Sample Output:**
```
User: Alice
Rank: 2.0
AFK: No
Muted: No

Chat msgs: 1234
Time: 15h 30m 45s
```

#### `afk [on|off]`
Sets the bot's AFK (Away From Keyboard) status.
- Use `afk on` to mark the bot as AFK
- Use `afk off` to mark the bot as active
- Use `afk` alone to see current status

**Examples:**
```
afk on
afk off
afk
```

---

### 💬 Chat Commands

#### `say <message>`
Makes the bot send a message to the main chat.

**Example:**
```
say Welcome everyone!
```

The bot will post: `Welcome everyone!` in the chat.

#### `pm <username> <message>`
Makes the bot send a private message to another user.

**Example:**
```
pm Alice Hello there!
```

The bot will PM Alice with: `Hello there!`

#### `clear`
**🔒 LEADER ONLY** - Clears the chat history for all users.

**Example:**
```
clear
```

**Note:** You must be the channel leader to use this command.

---

### 🎵 Playlist Commands

#### `playlist [number]`
Shows the current playlist. You can optionally specify how many items to show (default is 10).
- Current playing video is marked with ►
- Shows video title and duration

**Examples:**
```
playlist
playlist 5
playlist 20
```

**Sample Output:**
```
Playlist (25 items):
► 1. Current Song (3m 45s)
  2. Next Video (5m 20s)
  3. Another Video (2m 15s)
  ... and 22 more
```

#### `current`
Shows detailed information about the currently playing video, including:
- Title and duration
- Who added it
- Video URL
- Whether it's temporary

**Example:**
```
current
```

**Sample Output:**
```
Title: Cool Music Video
Duration: 4m 12s
Queued by: Alice
URL: https://youtube.com/watch?v=xyz
Temporary: No
```

#### `add <url> [temp]`
Adds a video to the playlist.
- `url` - The video URL (YouTube, Vimeo, etc.)
- `temp` - Optional: Use `yes` or `temp` to add as temporary (auto-deletes after playing)

**Examples:**
```
add https://youtube.com/watch?v=abc123
add https://youtube.com/watch?v=abc123 yes
add https://youtu.be/xyz789 temp
```

#### `remove <position>`
Removes a video from the playlist by its position number.

**Example:**
```
remove 5
```

This removes the 5th video in the playlist.

#### `move <from> <to>`
Moves a video from one position to another in the playlist.

**Example:**
```
move 5 2
```

This moves the video at position 5 to position 2.

#### `jump <position>`
**🔒 LEADER ONLY** - Jumps to a specific video in the playlist.

**Example:**
```
jump 10
```

Skips to the 10th video in the playlist.

**Note:** You must be the channel leader to use this command.

#### `next`
**🔒 LEADER ONLY** - Skips to the next video in the playlist.

**Example:**
```
next
```

**Note:** You must be the channel leader to use this command.

---

### ⚙️ Control Commands

#### `pause`
**🔒 LEADER ONLY** - Pauses or unpauses the currently playing video.

**Example:**
```
pause
```

**Note:** You must be the channel leader to use this command.

#### `kick <username> [reason]`
Kicks a user from the channel. You can optionally provide a reason.

**Examples:**
```
kick SpamBot
kick BadUser Inappropriate behavior
```

#### `voteskip`
Shows the current voteskip status (how many votes to skip the current video).

**Example:**
```
voteskip
```

**Sample Output:**
```
Voteskip: 3 / 5
```

---

## Tips and Tricks

### 💡 Helpful Hints

1. **Commands are case-insensitive** - `INFO`, `info`, and `Info` all work the same way.

2. **No need to type the bot's name** - Just type the command directly in the PM window.

3. **Multiple commands** - You can send multiple commands one after another. The bot will respond to each one.

4. **Short responses** - Responses are automatically split into multiple messages if they're too long for the PM window.

5. **Check your rank** - If commands aren't working, make sure you're a moderator (rank 2.0+).

### 📝 Common Use Cases

**Check who's online:**
```
users
```

**Add a video to the queue:**
```
add https://youtube.com/watch?v=abc123
```

**See what's playing:**
```
current
```

**Remove a duplicate video:**
```
playlist 20
remove 15
```

**Check user statistics:**
```
user Bob
```

**Send an announcement:**
```
say Server maintenance in 5 minutes!
```

---

## Troubleshooting

### The bot doesn't respond to my commands

**Possible causes:**
1. ✋ You're not a moderator (rank 2.0+) - Ask a channel admin to promote you
2. 🤖 The bot is offline - Check if it's still in the user list
3. 📝 You made a typo - Double-check the command spelling
4. ⏱️ The bot is slow - Wait a few seconds for a response

### Leader-only commands don't work

Some commands require you to be the **channel leader**:
- `clear` - Clear chat
- `pause` - Pause/unpause video
- `jump` - Jump to video
- `next` - Skip to next video

To become leader, you can:
1. Ask someone to give you leader with `/leader YourName` in chat
2. Use a channel admin account which may have automatic leader privileges

### I got an error message

The bot will tell you if:
- ❌ You used incorrect syntax - Check the command format above
- ❌ A user doesn't exist - Verify the username spelling
- ❌ A video can't be added - Make sure the URL is valid
- ❌ You don't have permission - You may need higher rank or leader status

---

## Need Help?

If you're having trouble using the bot:

1. **Try the help command** - Type `help` to see the command list
2. **Check your rank** - Make sure you're a moderator (rank 2.0+)
3. **Ask a channel admin** - They can help with permissions
4. **Test simple commands first** - Try `info` or `users` to make sure it's working

---

**Happy bot controlling! 🤖**
