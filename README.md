# Redis CLI Chat Application
> **Last Updated:** 2026-01-07  


A simple but powerful CLI chat application using Upstash Redis for persistent messaging.

## Features

- ✅ **Single Chat Room** - One unified chat space for all users
- ✅ **Custom Usernames** - Choose any username when joining
- ✅ **Message History** - View last 20 messages with timestamps
- ✅ **Interactive Mode** - Easy-to-use command interface
- ✅ **Background Streaming** - Real-time message updates while typing
- ✅ **Timestamps** - Each message includes exact timestamp
- ✅ **Colorized Output** - Beautiful terminal UI with colors

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Environment Variables

The `.env` file is already configured with your Upstash credentials:

```
UPSTASH_REDIS_REST_URL="https://glad-coyote-12496.upstash.io"
UPSTASH_REDIS_REST_TOKEN="ATDQAAIncDJkMGMyZGE3MTViYjI0NWMyYmU2YzA0NWY2OWViNDM0YXAyMTI0OTY"
```

### 3. Run the Application

```bash
python chat.py
```

### 4. Setup Gemini AI (Optional)
To use the AI chatbot features:
1. Obtain an API key from [Google AI Studio](https://makersuite.google.com/app/apikey).
2. Either add it to your local `.env` file:
   ```
   GEMINI_API_KEY="your_api_key_here"
   ```
3. OR use the shared key feature inside the app:
   ```
   /set_gemini_key your_api_key_here
   ```
   This saves the key to the shared Redis storage so everyone on the team can use it without needing their own key!

## Commands

| Command | Description |
|---------|-------------|
| `/history` | Display last 20 messages |
| `/gemini` | Enter AI Chat Mode 🤖 |
| `/set_gemini_key <key>` | Share an API key with the group 🔑 |
| `@user /silent <msg>` | Send a private message 🤫 |
| `/help` | Show help menu |
| `/quit` | Exit the application |
| Any text | Send a message |

## Message Format

Each message stores:
- **Username** - Who sent it
- **Message** - The actual message content
- **Timestamp** - When it was sent (YYYY-MM-DD HH:MM:SS)
- **Recipients** - For private messages
- **Is Silent** - Flag for private messages

## How It Works

- Messages are stored in Upstash Redis using a list (LPUSH)
- Background thread checks for new messages every 1 second
- New messages appear in real-time while you're typing
- **Gemini Integration**: 
  - The app first checks your local `.env` for a key.
  - If missing (or is a placeholder), it fetches the shared key from Redis (`chat:config:gemini_key`).
  - This allows seamless AI usage for all team members.

## Technical Stack

- **Python 3.x**
- **Upstash Redis** (REST API)
- **Google Generative AI** (Gemini)
- **Requests** - HTTP library for Redis communication
- **Threading** - Background message streaming
- **Colorama** - Terminal colors
- **python-dotenv** - Environment variable management

## Example Session

```
============================================================
Welcome to Redis Chat CLI!
============================================================

Enter your username: Alice

--- New message(s) received ---
[2026-01-02 10:30:45] Bob: Hey everyone!
[2026-01-02 10:31:12] Charlie: Hello!

>>> /gemini
============================================================
Entered Gemini AI CLI Mode
Type your prompt or /exit to return to chat
============================================================

Gemini > Write a poem about coding
Thinking...
In realms of logic, lines involved,
A digital tapestry evolved...

Gemini > /exit
Exiting Gemini Mode...

>>> /set_gemini_key AIzaSy...
✓ Gemini API Key saved to shared storage! Friends can now use it.

>>> Hi there!
✓ Message sent
```
## Star History

Enjoy chatting! 🚀
