# Gemini AI Backend Integration

The chat application now uses a **Redis-backed Gemini AI integration** instead of local API keys.

## How It Works

1. **User sends prompt**: When you use `/gemini` command and enter a prompt, the message is pushed to a Redis queue.
   - Queue Key: `chat:gemini:queue`
   - Each prompt includes: user, prompt text, unique ID, and timestamp

2. **Backend processes**: A backend service (running separately) listens to the queue:
   - Reads prompts from Redis queue
   - Sends them to Gemini API
   - Stores responses back in Redis

3. **User receives response**: The CLI polls Redis for the response:
   - Response Key: `chat:gemini:response:{prompt_id}`
   - Maximum wait time: 30 seconds
   - Responses are auto-deleted after retrieval

## Setup

No local API key needed! Just ensure:
- Redis credentials are set in `.env` (UPSTASH_REDIS_REST_URL, UPSTASH_REDIS_REST_TOKEN)
- A backend service is running that processes the Gemini queue

## Backend Service Requirements

Your backend service should:
1. Listen to: `chat:gemini:queue`
2. For each prompt JSON:
   ```json
   {
     "id": "username_timestamp",
     "user": "username",
     "prompt": "user's prompt text",
     "timestamp": "2026-01-07T..."
   }
   ```
3. Send to Gemini API and store response:
   ```json
   {
     "response": "Gemini's response text"
   }
   ```
   Or on error:
   ```json
   {
     "error": "error message"
   }
   ```
4. Store in: `chat:gemini:response:{prompt_id}` with any reasonable TTL (e.g., 60 seconds)

## Example Backend (Node.js/Python)

You'll need to create a separate service that:
- Connects to Redis
- Uses `BLPOP` or similar to listen for prompts
- Calls Gemini API with the prompt
- Stores responses back in Redis with the matching ID

## No Local Keys

- ✅ No GEMINI_API_KEY in `.env` 
- ✅ No user prompt for API key
- ✅ All API handling centralized on backend
- ✅ Secure and scalable
