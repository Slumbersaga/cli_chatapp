# Update Log - 06.01.2026

## New Features

### 1. 🤖 Gemini AI Integration
- **CLI Mode**: A dedicated interactive interface for chatting with Google's Gemini AI.
- **Usage**: Type `/gemini` to enter the mode.
- **Features**: 
  - Contextual conversation.
  - Type `/exit` to return to the main chat.

### 2. @ Mentions & Notifications
- **Direct Mentions**: Mention users using `@username` (e.g., `@alice`).
- **@everyone**: Notify all users in the chat with `@everyone`.
- **Notifications**: 
  - Highlights mentions in **Yellow**.
  - Sends desktop notifications (using `plyer`) when you are mentioned or `@everyone` is called, even if the window is in the background.

### 3. 🤫 Silent / Private Messages
- **Safe Messaging**: Send messages visible ONLY to mentioned users.
- **Usage**: Mention a user and add `/silent` (e.g., `@bob /silent Secret plan`).
- **Visibility**:
  - Sender sees it (`[SILENT]` in Magenta).
  - Recipient sees it.
  - Others do **not** see it at all.

### 4. ✨ User Autocomplete
- **Smart Input**: As you type `@`, a dropdown list of active users appears.
- **Controls**: Use `Tab` or `Arrow Keys` to select a user.
- **Dynamic**: The user list updates automatically based on chat activity.

## Installation

The following dependencies have been added:
- `google-generativeai`
- `prompt_toolkit`

To update your environment:
```bash
pip install -r requirements.txt
```

## Configuration

Ensure your `.env` file includes the Gemini API key:
```env
GEMINI_API_KEY="AIzaSyDu1Pp2VnU_w_qRuLOVS3lo3ZQGdko10go"
```
