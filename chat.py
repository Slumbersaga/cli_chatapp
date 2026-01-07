# Last Updated: 2026-01-07
# Description: Redis-based CLI Chat Application with Gemini AI integration
import os
import requests
import json
import time
import threading
import re
import os
from datetime import datetime
from dotenv import load_dotenv
from colorama import Fore, Style, init
import ctypes
import platform

def enable_vt_processing():
    """Enable VT100 emulation on Windows"""
    if platform.system() == "Windows":
        try:
            kernel32 = ctypes.windll.kernel32
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            # Get current mode
            hStdOut = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(hStdOut, ctypes.byref(mode))
            # Set mode
            mode.value |= 0x0004
            kernel32.SetConsoleMode(hStdOut, mode)
        except:
            pass

enable_vt_processing()

try:
    from plyer import notification
    PLYER_AVAILABLE = True
except ImportError:
    PLYER_AVAILABLE = False


try:
    import warnings
    warnings.simplefilter("ignore", category=FutureWarning)
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    
# Windows ANSI Fix
os.system('')

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.patch_stdout import patch_stdout
    from prompt_toolkit.styles import Style as PromptStyle
    from prompt_toolkit import print_formatted_text
    from prompt_toolkit.formatted_text import ANSI
    PROMPT_TOOLKIT_AVAILABLE = True
except ImportError:
    PROMPT_TOOLKIT_AVAILABLE = False

# Initialize colorama
# strip=False ensures we send raw ANSI codes which prompt_toolkit/Windows Terminal can handle
init(autoreset=True, strip=False)

# Load environment variables
load_dotenv()

# Redis Configuration (Loaded from .env)
REDIS_URL = os.getenv("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if GEMINI_API_KEY and "paste_your_gemini_api_key" in GEMINI_API_KEY:
    GEMINI_API_KEY = None

# Simple color theme
PRIMARY_COLOR = Fore.GREEN
USERNAME_COLOR = Fore.WHITE
MENTION_COLOR = Fore.YELLOW
SILENT_COLOR = Fore.MAGENTA
ERROR_COLOR = Fore.RED

if not REDIS_URL or not REDIS_TOKEN:
    print(ERROR_COLOR + "Error: Missing UPSTASH_REDIS_REST_URL or UPSTASH_REDIS_REST_TOKEN in .env")
    print(ERROR_COLOR + "Please check your .env file.")
    # Keep window open if double-clicked
    input("Press Enter to exit...")
    exit(1)

CHAT_KEY = "chat:messages"
USERS_KEY = "chat:users"
CONFIG_GEMINI_KEY = "chat:config:gemini_key"

# Custom Completer for @mentions
class UserCompleter(Completer):
    def __init__(self, get_users_func):
        self.get_users_func = get_users_func

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        word = text.split(' ')[-1]
        
        if word.startswith('@'):
            search = word[1:].lower()
            users = self.get_users_func()
            for user in users:
                if user.lower().startswith(search):
                    yield Completion(
                        f"@{user}", 
                        start_position=-len(word),
                        display=f"@{user}",
                        style="class:mention"
                    )

class RedisChat:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {REDIS_TOKEN}",
            "Content-Type": "application/json"
        }
        self.username = None
        self.running = True
        self.message_counter = 0
        self.known_users = set()
        self.users_lock = threading.Lock()
        self.active_user_count = 1
        
        # Try to load Gemini Key from Redis if not in Env
        global GEMINI_API_KEY
        if not GEMINI_API_KEY and GEMINI_AVAILABLE:
            print(PRIMARY_COLOR + "\nNo local Gemini API Key found.")
            user_key = input(PRIMARY_COLOR + "Enter your Gemini API Key directly (or press Enter to use the Shared System Key): ").strip()
            
            if user_key and len(user_key) > 10:
                GEMINI_API_KEY = user_key
                genai.configure(api_key=GEMINI_API_KEY)
                print(PRIMARY_COLOR + "✓ Using provided API Key")
                
                # Optional: Offer to save to .env
                save_env = input(PRIMARY_COLOR + "Save this key to .env for future use? (y/n): ").strip().lower()
                if save_env == 'y':
                    try:
                        with open('.env', 'a') as f:
                            f.write(f'\nGEMINI_API_KEY="{user_key}"')
                        print(PRIMARY_COLOR + "✓ Saved to .env")
                    except:
                        pass
            else:
                 print(PRIMARY_COLOR + "⚠ No key provided. Attempting to fetch Shared System Key...")
                 self.fetch_gemini_key_from_redis()
            
    def fetch_gemini_key_from_redis(self):
        """Fetch Gemini API key from Redis shared storage"""
        print(PRIMARY_COLOR + "Checking Redis for shared Gemini API key...")
        global GEMINI_API_KEY
        key = None
        
        try:
            response = self.redis_request("GET", [CONFIG_GEMINI_KEY])
            if response and response.get("result"):
                key = response["result"]
                print(PRIMARY_COLOR + "✓ Loaded Gemini API Key from sync storage")
            else:
                print(ERROR_COLOR + "⚠ No Gemini API Key found in shared storage.")
                print(ERROR_COLOR + "  Use /set_gemini_key <key> to configure it for everyone.")
        except Exception as e:
            print(ERROR_COLOR + f"Failed to fetch key from Redis: {e}")

        if key:
            try:
                genai.configure(api_key=key)
                GEMINI_API_KEY = key
            except Exception as e:
                print(ERROR_COLOR + f"Failed to configure Gemini: {e}")

    def set_gemini_key_in_redis(self, key):
        """Securely save Gemini API key to Redis"""
        if not key.strip():
            print(ERROR_COLOR + "Invalid key")
            return
        
        try:
            self.redis_request("SET", [CONFIG_GEMINI_KEY, key])
            print(PRIMARY_COLOR + "✓ Gemini API Key saved to shared storage! Friends can now use it.")
            # Also configure locally
            genai.configure(api_key=key)
            global GEMINI_API_KEY
            GEMINI_API_KEY = key
        except Exception as e:
             print(ERROR_COLOR + f"Failed to save key: {e}")

        
    def update_known_users(self, users_list=None):
        if users_list:
            with self.users_lock:
                self.known_users.update(users_list)
                
    def get_known_users(self):
        with self.users_lock:
            # Always include 'everyone'
            full_list = {'everyone'} | self.known_users
            # Exclude self if possible, but for mentions self is okay
            return list(full_list)

    def register_user(self):
        """Add self to active users list"""
        if self.username:
            self.redis_request("SADD", [USERS_KEY, self.username])
        
    def is_window_focused(self):
        """Check if the terminal window is in foreground"""
        try:
            hwnd = ctypes.windll.kernel32.GetConsoleWindow()
            if hwnd == 0: return False
            return hwnd == ctypes.windll.user32.GetForegroundWindow()
        except:
            return False
        
    def redis_request(self, command, args=None):
        """Make HTTP request to Upstash Redis REST API"""
        try:
            # Format: ["COMMAND", "arg1", "arg2", ...]
            cmd_list = [command]
            if args:
                cmd_list.extend(args)
            
            response = requests.post(
                f"{REDIS_URL}",
                json=cmd_list,
                headers=self.headers,
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(PRIMARY_COLOR + f"Redis error: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            print(PRIMARY_COLOR + f"Connection error: {e}")
            return None
    
    def send_message(self, message):
        """Send a message to the chat handling mentions and silent mode"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Parse for /silent and recipients
        recipients = []
        is_silent = False
        display_text = message
        
        # formatting mentions and checking for silent
        if "/silent" in message:
            is_silent = True
            display_text = message.replace("/silent", "").strip()
            # If silent, whoever is mentioned is a recipient
            # We assume mentions are in the format @username
            matches = re.findall(r'@(\w+)', message)
            if matches:
                 recipients = matches
            else:
                # /silent used but no mentions? Maybe just warn user or treat as private note to self?
                # For now let's assume it's private to self if no mentions
                pass

        msg_data = {
            "username": self.username,
            "message": display_text,
            "timestamp": timestamp,
            "recipients": recipients if is_silent else [],
            "is_silent": is_silent
        }
        
        msg_json = json.dumps(msg_data)
        result = self.redis_request("LPUSH", [CHAT_KEY, msg_json])
        
        if result:
            if is_silent:
                print(SILENT_COLOR + "✓ Silent message sent")
            else:
                print(PRIMARY_COLOR + "✓ Message sent")
        else:
            print(ERROR_COLOR + "✗ Failed to send message")
    
    def get_message_history(self, count=10):
        """Get chat history from Redis"""
        result = self.redis_request("LRANGE", [CHAT_KEY, 0, count - 1])
        
        if result and result.get("result"):
            messages = []
            for msg_str in result["result"]:
                try:
                    msg = json.loads(msg_str)
                    messages.append(msg)
                except:
                    pass
            return messages
        return []
    
    def display_message(self, msg):
        """Display a single message with formatting"""
        username = msg.get("username", "Unknown")
        message = msg.get("message", "")
        timestamp = msg.get("timestamp", "")
        recipients = msg.get("recipients", [])
        is_silent = msg.get("is_silent", False)
        
        # VISIBILITY CHECK
        # If silent, only show if I am the sender OR I am in recipients
        if is_silent:
            if self.username != username and self.username not in recipients:
                return

        # Formatting
        display_prefix = ""
        user_color = USERNAME_COLOR
        msg_color = PRIMARY_COLOR # Default message color (Green)

        if is_silent:
            display_prefix = f"{SILENT_COLOR}[SILENT] "
            msg_color = SILENT_COLOR # Silent messages in Magenta

        # Highlight mentions in the message body
        # logic: replace @MyName with colored version
        if self.username:
            # Highlight all mentions (words starting with @)
            def replace_mention(match):
                mention_text = match.group(0)
                # If it is @everyone or @any_other_user, color it yellow
                return f"{MENTION_COLOR}{mention_text}{msg_color}"
            
            message = re.sub(r'@\w+', replace_mention, message)

        final_str = f"{PRIMARY_COLOR}[{timestamp}] {display_prefix}{user_color}{username}{PRIMARY_COLOR}: {msg_color}{message}"
        
        if PROMPT_TOOLKIT_AVAILABLE:
            print_formatted_text(ANSI(final_str))
        else:
            print(final_str)
    
    def show_history(self):
        """Display chat history"""
        print(PRIMARY_COLOR + "\n" + "="*60)
        print(PRIMARY_COLOR + "Chat History (Latest 20 messages)")
        print(PRIMARY_COLOR + "="*60)
        
        messages = self.get_message_history(20)
        
        if not messages:
            print(PRIMARY_COLOR + "No messages yet. Be the first to chat!")
        else:
            # Reverse to show oldest first
            for msg in reversed(messages):
                self.display_message(msg)
        
        print(PRIMARY_COLOR + "="*60 + "\n")
    
    def stream_updates(self):
        """Background thread to check for new messages and update presence"""
        ONLINE_USERS_KEY = "chat:online_users_zset"
        
        while self.running:
            try:
                # 1. HEARTBEAT & PRESENCE
                now = int(time.time())
                
                # Pipeline-like execution (manually chained for REST API simplicity)
                # A. Heartbeat: Update my score to current time
                if self.username:
                    self.redis_request("ZADD", [ONLINE_USERS_KEY, str(now), self.username])
                
                # B. Cleanup: Remove users inactive for > 15 seconds
                cutoff = now - 15
                self.redis_request("ZREMRANGEBYSCORE", [ONLINE_USERS_KEY, "-inf", str(cutoff)])
                
                # C. Fetch online count & users
                card_response = self.redis_request("ZCARD", [ONLINE_USERS_KEY])
                if card_response and "result" in card_response:
                     self.active_user_count = card_response["result"]
                     
                # Update known users for autocomplete (optional: fetch actual list)
                # users_response = self.redis_request("ZRANGE", [ONLINE_USERS_KEY, 0, -1])
                # if users_response and "result" in users_response:
                #      self.update_known_users(users_response["result"])

                # 2. MESSAGES
                result = self.redis_request("LLEN", [CHAT_KEY])
                
                if result and result.get("result") is not None:
                    current_count = result["result"]
                    
                    if current_count > self.last_count:
                        new_messages_count = current_count - self.last_count
                        messages = self.get_message_history(new_messages_count)
                        
                        if messages:
                            if not PROMPT_TOOLKIT_AVAILABLE:
                                print(PRIMARY_COLOR + "\n--- New message(s) received ---")
                            else:
                                print_formatted_text(ANSI(f"{PRIMARY_COLOR}\n--- New message(s) received ---"))
                            
                            # Check if we should notify (background & not own message)
                            if PLYER_AVAILABLE and not self.is_window_focused():
                                # Filter messages that are relevant for notification
                                relevant_msgs = []
                                for msg in messages:
                                    sender = msg.get("username", "Unknown")
                                    if sender != "Unknown":
                                        self.update_known_users([sender])

                                    if sender == self.username:
                                        continue
                                        
                                    text = msg.get("message", "")
                                    recipients = msg.get("recipients", [])
                                    is_silent = msg.get("is_silent", False)

                                    # Visibility check for notification
                                    if is_silent and self.username not in recipients:
                                        continue
                                    
                                    # Add to potential notifications
                                    relevant_msgs.append((sender, text))

                                # Notify only ONCE per batch if there are relevant messages
                                if relevant_msgs:
                                    # Prioritize the LATEST message (messages[0] is newest)
                                    last_sender, last_text = relevant_msgs[0]
                                    
                                    # Check for mentions in ANY of the messages to upscale the alert
                                    is_mention = False
                                    notif_title = "Redis Chat"
                                    
                                    # Scan for high priority alerts
                                    for s, t in relevant_msgs:
                                        t_lower = t.lower()
                                        if "@everyone" in t_lower:
                                            notif_title = "📢 @everyone Mentioned!"
                                            is_mention = True
                                            break
                                        if f"@{self.username.lower()}" in t_lower:
                                            notif_title = "🔔 You were mentioned!"
                                            is_mention = True
                                            break
                                    
                                    if not is_mention:
                                        notif_title = f"New message from {last_sender}"

                                    try:
                                        notification.notify(
                                            title=notif_title,
                                            message=f"{last_sender}: {last_text}",
                                            app_name="Redis Chat CLI",
                                            timeout=5
                                        )
                                    except Exception:
                                        pass
                                        
                            for msg in messages:
                                self.display_message(msg)
                            
                            # Refresh prompt (Visual only)
                            # Logic handled by loop below
                        
                        self.last_count = current_count
                
                time.sleep(1)  # Check for new messages every second
            except Exception as e:
                # print(PRIMARY_COLOR + f"Stream error: {e}") # Suppress noise
                time.sleep(2)
    
    def start_stream_thread(self):
        """Start background streaming thread"""
        stream_thread = threading.Thread(target=self.stream_updates, daemon=True)
        stream_thread.start()
    
    def get_username(self):
        """Get username from user"""
        while True:
            username = input(PRIMARY_COLOR + "Enter your username: ").strip()
            if username and len(username) <= 20:
                self.username = username
                self.register_user() # Register in Redis
                self.update_known_users([username])
                print(PRIMARY_COLOR + f"Welcome, {USERNAME_COLOR}{username}{PRIMARY_COLOR}!")
                break
            else:
                print(PRIMARY_COLOR + "Username must be 1-20 characters")
    
    def show_help(self):
        """Display help menu"""
        print(PRIMARY_COLOR + "\n" + "="*60)
        print(PRIMARY_COLOR + "Commands:")
        print(PRIMARY_COLOR + "="*60)
        print(f"{PRIMARY_COLOR}/history  - Show chat history")
        print(f"{PRIMARY_COLOR}/gemini   - Switch to Gemini AI CLI")
        print(f"{PRIMARY_COLOR}/help     - Show this help menu")
        print(f"{PRIMARY_COLOR}/quit     - Exit the chat")
        print(f"{PRIMARY_COLOR}/set_gemini_key [key] - Securely sync API key with friends")
        print(f"{PRIMARY_COLOR}@user /silent [msg] - Send private message")
        print(f"{PRIMARY_COLOR}Any text   - Send a message")
        print(PRIMARY_COLOR + "="*60 + "\n")

    def start_gemini_cli(self):
        """Start interactive Gemini CLI session"""
        if not GEMINI_AVAILABLE:
            print(PRIMARY_COLOR + "Error: google-generativeai package not installed")
            return
        if not GEMINI_API_KEY:
            print(PRIMARY_COLOR + "Error: GEMINI_API_KEY not found in .env")
            return

        print(PRIMARY_COLOR + "\n" + "="*60)
        print(PRIMARY_COLOR + "Entered Gemini AI CLI Mode")
        print(PRIMARY_COLOR + "Type your prompt or /exit to return to chat")
        print(PRIMARY_COLOR + "="*60 + "\n")

        model = genai.GenerativeModel('gemini-1.5-flash')
        chat_session = model.start_chat(history=[])

        while True:
            try:
                user_input = input(Fore.MAGENTA + "Gemini > " + Style.RESET_ALL).strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == "/exit":
                    print(PRIMARY_COLOR + "Exiting Gemini Mode...\n")
                    break
                
                print(Fore.YELLOW + "Thinking...", end="\r")
                try:
                    response = chat_session.send_message(user_input)
                    print(" " * 20, end="\r") # Clear 'Thinking...'
                    print(Fore.WHITE + response.text + "\n")
                except Exception as e:
                    print(Fore.RED + f"\nError from Gemini: {e}\n")
                    
            except KeyboardInterrupt:
                print("\nReturning to main chat...")
                break
    
    def run(self):
        """Main chat loop"""
        # Display Banner
        if os.path.exists("banner.txt"):
            try:
                with open("banner.txt", "r", encoding="utf-8") as f:
                    banner = f.read()
                print(Fore.MAGENTA + Style.BRIGHT + banner)
            except:
                pass
        
        print(PRIMARY_COLOR + "Welcome to Redis Chat CLI!")
        print(PRIMARY_COLOR + "="*60 + "\n")
        
        # Initialize last_count BEFORE starting thread/loop
        # Fetch current message count so we don't alert on old history
        try:
             result = self.redis_request("LLEN", [CHAT_KEY])
             self.last_count = result["result"] if (result and result.get("result")) else 0
        except:
             self.last_count = 0

        self.get_username()
        self.start_stream_thread()
        self.show_history()
        self.show_help()
        
        print(PRIMARY_COLOR + "Connected! Type your message or /help for commands\n")
        
        if PROMPT_TOOLKIT_AVAILABLE:
            # Setup prompt session with autocomplete
            style = PromptStyle.from_dict({
                'prompt': '#00ff00 bold',
                'mention': '#ffff00',
            })
            session = PromptSession(
                completer=UserCompleter(self.get_known_users),
                style=style
            )

        try:
            while self.running:
                try:
                    # Dynamic colorful prompt
                    prompt_str = f"{Fore.CYAN}[{Fore.GREEN}Live:{Fore.YELLOW}{self.active_user_count}{Fore.CYAN}] {Fore.GREEN}>>> {Style.RESET_ALL}"
                    
                    if PROMPT_TOOLKIT_AVAILABLE:
                        # prompt_toolkit handles ANSI codes when wrapped in ANSI()
                        # But session.prompt takes a string or formatted text.
                        # Simple string with ANSI codes often works in terminal.
                        with patch_stdout():
                             message = session.prompt(ANSI(prompt_str)).strip()
                    else:
                        message = input(prompt_str).strip()
                    
                    if not message:
                        continue
                    
                    if message.lower() == "/quit":
                        self.running = False
                        print(PRIMARY_COLOR + "Goodbye!")
                        break
                    elif message.lower() == "/help":
                        self.show_help()
                    elif message.lower() == "/history":
                        self.show_history()
                    elif message.lower() == "/gemini":
                        self.start_gemini_cli()
                    elif message.lower().startswith("/set_gemini_key"):
                        parts = message.split(' ')
                        if len(parts) > 1:
                            self.set_gemini_key_in_redis(parts[1])
                        else:
                            print(ERROR_COLOR + "Usage: /set_gemini_key <your_api_key>")
                    else:
                        self.send_message(message)
                
                except KeyboardInterrupt:
                    self.running = False
                    print(PRIMARY_COLOR + "\nGoodbye!")
                    break
        
        except Exception as e:
            print(PRIMARY_COLOR + f"Error: {e}")
        
        self.running = False

if __name__ == "__main__":
    chat = RedisChat()
    chat.run()
