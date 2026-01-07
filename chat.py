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
import random
import sys

class Effects:
    @staticmethod
    def typewriter(text, speed=0.03, color=Fore.GREEN):
        """Print text character by character"""
        for char in text:
            sys.stdout.write(color + char)
            sys.stdout.flush()
            time.sleep(speed)
        print() # Newline at end

    @staticmethod
    def matrix_glitch(banner_text, duration=1.5):
        """Simulate a CRT scanline or glitch effect on the banner"""
        lines = banner_text.split('\n')
        end_time = time.time() + duration
        
        while time.time() < end_time:
            # Clear screen (cursor home)
            print('\033[H', end='')
            
            # Random bright scanline position
            scanline = random.randint(0, len(lines)-1)
            
            for i, line in enumerate(lines):
                if i == scanline:
                    # Bright white line for scanline effect
                    print(Fore.WHITE + Style.BRIGHT + line + Style.RESET_ALL)
                else:
                    # Normal purple for rest
                    # Occasionally glitch a character
                    if random.random() < 0.02:
                        glitched = list(line)
                        if glitched:
                            idx = random.randint(0, len(glitched)-1)
                            glitched[idx] = random.choice(['#', '$', '%', '&', '0', '1'])
                            print(Fore.MAGENTA + Style.DIM + "".join(glitched) + Style.RESET_ALL)
                        else:
                            print(Fore.MAGENTA + Style.DIM + line + Style.RESET_ALL)
                    else:
                        print(Fore.MAGENTA + Style.NORMAL + line + Style.RESET_ALL)
            
            time.sleep(0.05)
        
        # Final clean render
        print('\033[H', end='')
        print(Fore.MAGENTA + Style.BRIGHT + banner_text + Style.RESET_ALL)

    @staticmethod
    def spinner(text, duration=2.0):
        """Show animated spinner"""
        chars = "|/-\\"
        end_time = time.time() + duration
        i = 0
        while time.time() < end_time:
            time.sleep(0.1)
            # \r to return to start of line
            sys.stdout.write(f"\r{Fore.MAGENTA}{chars[i % 4]} {Fore.GREEN}{text}")
            sys.stdout.flush()
            i += 1
        # Clear spinner line
        sys.stdout.write(f"\r{Fore.GREEN}✓ {text}          \n")
        sys.stdout.flush()


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
    from prompt_toolkit.lexers import Lexer
    PROMPT_TOOLKIT_AVAILABLE = True

    class CommandLexer(Lexer):
        def lex_document(self, document):
            def get_line_tokens(lineno):
                line = document.lines[lineno]
                tokens = []
                # Simple tokenization by splitting on space to find commands
                # This is a basic implementation
                parts = line.split(' ')
                current_len = 0
                
                for i, part in enumerate(parts):
                    if part.startswith('/'):
                        tokens.append(('class:command', part))
                    elif part.startswith('@'):
                        tokens.append(('class:mention', part))
                    else:
                        tokens.append(('class:text', part))
                    
                    # Add space if not the last part
                    if i < len(parts) - 1:
                        tokens.append(('', ' '))
                
                return tokens
            return get_line_tokens

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
GEMINI_QUEUE_KEY = "chat:gemini:queue"
GEMINI_RESPONSE_KEY = "chat:gemini:response:{}"

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
        last_heartbeat = 0
        last_cleanup = 0
        heartbeat_interval = 20  # Send heartbeat every 20 seconds (was: every 1 second via message polling)
        cleanup_interval = 60    # Cleanup stale users every 60 seconds (was: every 1 second)
        
        while self.running:
            try:
                now = int(time.time())
                
                # 1. HEARTBEAT - Only every 20 seconds
                if self.username and (now - last_heartbeat) >= heartbeat_interval:
                    self.redis_request("ZADD", [ONLINE_USERS_KEY, str(now), self.username])
                    last_heartbeat = now
                
                # 2. CLEANUP - Only every 60 seconds
                if (now - last_cleanup) >= cleanup_interval:
                    cutoff = now - 15
                    self.redis_request("ZREMRANGEBYSCORE", [ONLINE_USERS_KEY, "-inf", str(cutoff)])
                    last_cleanup = now

                # 3. MESSAGE CHECK - Every 2-3 seconds (was: every 1 second)
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
                
                time.sleep(2)  # Check for new messages every 2 seconds (reduced from 1s)
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
        CMD = Fore.MAGENTA
        DESC = PRIMARY_COLOR
        
        print(PRIMARY_COLOR + "\n" + "="*60)
        print(PRIMARY_COLOR + "Commands:")
        print(PRIMARY_COLOR + "="*60)
        print(f"{CMD}/history{DESC}  - Show chat history")
        print(f"{CMD}/gemini{DESC}   - Switch to Gemini AI CLI (Redis backend)")
        print(f"{CMD}/help{DESC}     - Show this help menu")
        print(f"{CMD}/quit{DESC}     - Exit the chat")
        print(f"{Fore.YELLOW}@user {CMD}/silent [msg]{DESC} - Send private message")
        print(f"{DESC}Any text   - Send a message")
        print(PRIMARY_COLOR + "="*60 + "\n")

    def start_gemini_cli(self):
        """Start interactive Gemini CLI session via Redis backend"""
        print(PRIMARY_COLOR + "\n" + "="*60)
        print(Effects.typewriter("Entered Gemini AI CLI Mode", color=Fore.MAGENTA))
        print(PRIMARY_COLOR + "Type your prompt or " + Fore.MAGENTA + "/exit" + PRIMARY_COLOR + " to return to chat")
        print(PRIMARY_COLOR + "(Powered by Redis backend)")
        print(PRIMARY_COLOR + "="*60 + "\n")

        while True:
            try:
                user_input = input(Fore.MAGENTA + "Gemini > " + Style.RESET_ALL).strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() == "/exit":
                    print(PRIMARY_COLOR + "Exiting Gemini Mode...\n")
                    break
                
                # Use Spinner for thinking
                Effects.spinner("Sending to backend...", duration=0.5)
                
                try:
                    # Push prompt to Redis queue
                    prompt_id = f"{self.username}_{int(time.time() * 1000)}"
                    self.redis_request("RPUSH", [GEMINI_QUEUE_KEY, json.dumps({
                        "id": prompt_id,
                        "user": self.username,
                        "prompt": user_input,
                        "timestamp": datetime.now().isoformat()
                    })])
                    
                    # Poll for response with timeout
                    response_key = GEMINI_RESPONSE_KEY.format(prompt_id)
                    max_wait = 30  # 30 seconds
                    waited = 0
                    
                    while waited < max_wait:
                        response = self.redis_request("GET", [response_key])
                        if response and response.get("result"):
                            result_data = json.loads(response["result"])
                            if "error" in result_data:
                                print(Fore.RED + f"\nError from backend: {result_data['error']}\n")
                            else:
                                print(Fore.WHITE + result_data.get("response", "No response") + "\n")
                            # Clean up response key
                            self.redis_request("DEL", [response_key])
                            break
                        
                        time.sleep(0.5)
                        waited += 0.5
                    
                    if waited >= max_wait:
                        print(Fore.YELLOW + "\nTimeout waiting for backend response (>30s)\n")
                        
                except Exception as e:
                    print(Fore.RED + f"\nError: {e}\n")
                    
            except KeyboardInterrupt:
                print("\nReturning to main chat...")
                break
    
    def run(self):
        """Main chat loop"""
        # Display Banner with fancy effects
        if os.path.exists("banner.txt"):
            try:
                with open("banner.txt", "r", encoding="utf-8") as f:
                    banner = f.read()
                
                # Clear screen initially
                os.system('cls' if os.name == 'nt' else 'clear')
                
                # Run the Glitch/Scanline effect
                Effects.matrix_glitch(banner)
                
            except:
                pass
        
        print("\n") # Spacer
        Effects.typewriter("Welcome to Redis Chat CLI...", speed=0.03, color=Fore.GREEN)
        Effects.spinner("Initializing secure connection...", duration=1.5)
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
        
        print(PRIMARY_COLOR + "Connected! Type your message or " + Fore.MAGENTA + "/help" + PRIMARY_COLOR + " for commands\n")
        
        if PROMPT_TOOLKIT_AVAILABLE:
            # Setup prompt session with autocomplete AND custom lexer for colors
            style = PromptStyle.from_dict({
                'prompt': '#00ff00 bold',
                'mention': '#ffff00',
                'command': '#ff00ff', # Magenta for commands
                'text': '#ffffff',
            })
            session = PromptSession(
                completer=UserCompleter(self.get_known_users),
                style=style,
                lexer=CommandLexer()
            )

        try:
            while self.running:
                try:
                    # Dynamic colorful prompt
                    prompt_str = f"[{self.active_user_count}] >>> "
                    # We'll rely on our custom style for the prompt if possible, or just pass simple ANSI
                    # For simplicity with current setup, we keep the ANSI prompt but use lexer for input
                    
                    ansi_prompt = f"{Fore.CYAN}[{Fore.GREEN}Live:{Fore.YELLOW}{self.active_user_count}{Fore.CYAN}] {Fore.GREEN}>>> {Style.RESET_ALL}"
                    
                    if PROMPT_TOOLKIT_AVAILABLE:
                         # session.prompt handles the input highlighting via lexer
                         message = session.prompt(ANSI(ansi_prompt)).strip()
                    else:
                        message = input(ansi_prompt).strip()
                    
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
