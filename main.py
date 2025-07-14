import asyncio
import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime

# Telegram libraries
from telethon import TelegramClient, events
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import RPCError

# Remove web server imports

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('userbot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration from environment variables
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
SESSION_STRING = os.getenv("SESSION_STRING", "")

# Global variables
userbot_client: Optional[TelegramClient] = None
control_bot: Optional[Client] = None
tasks: List[Dict] = []
forwarding_active = {}

# Remove web server code - focus on bots only

class TaskManager:
    """Manages forwarding tasks and storage"""
    
    def __init__(self, filename: str = "tasks.json"):
        self.filename = filename
        self.load_tasks()
    
    def load_tasks(self):
        """Load tasks from JSON file"""
        global tasks
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r') as f:
                    tasks = json.load(f)
            else:
                tasks = []
                self.save_tasks()
            logger.info(f"Loaded {len(tasks)} tasks from {self.filename}")
        except Exception as e:
            logger.error(f"Error loading tasks: {e}")
            tasks = []
    
    def save_tasks(self):
        """Save tasks to JSON file"""
        try:
            with open(self.filename, 'w') as f:
                json.dump(tasks, f, indent=2)
            logger.info(f"Saved {len(tasks)} tasks to {self.filename}")
        except Exception as e:
            logger.error(f"Error saving tasks: {e}")
    
    def add_task(self, source: str, target: str) -> int:
        """Add a new forwarding task"""
        task = {
            "id": len(tasks),
            "source": source,
            "target": target,
            "on": True,
            "created_at": datetime.now().isoformat()
        }
        tasks.append(task)
        self.save_tasks()
        return task["id"]
    
    def delete_task(self, task_id: int) -> bool:
        """Delete a task by ID"""
        global tasks
        if 0 <= task_id < len(tasks):
            tasks.pop(task_id)
            # Reindex tasks
            for i, task in enumerate(tasks):
                task["id"] = i
            self.save_tasks()
            return True
        return False
    
    def toggle_task(self, task_id: int, status: bool) -> bool:
        """Enable/disable a task"""
        if 0 <= task_id < len(tasks):
            tasks[task_id]["on"] = status
            self.save_tasks()
            return True
        return False
    
    def get_task(self, task_id: int) -> Optional[Dict]:
        """Get a task by ID"""
        if 0 <= task_id < len(tasks):
            return tasks[task_id]
        return None
    
    def get_all_tasks(self) -> List[Dict]:
        """Get all tasks"""
        return tasks

# Initialize task manager
task_manager = TaskManager()

async def resolve_chat_id(client, chat_identifier: str):
    """Resolve chat ID from username or ID"""
    try:
        if chat_identifier.startswith('@'):
            # Username
            entity = await client.get_entity(chat_identifier)
            return entity.id
        else:
            # Try as numeric ID
            chat_id = int(chat_identifier)
            return chat_id
    except Exception as e:
        logger.error(f"Error resolving chat ID for {chat_identifier}: {e}")
        return None

async def setup_userbot():
    """Initialize and start the UserBot"""
    global userbot_client
    
    if not SESSION_STRING:
        logger.error("SESSION_STRING not found. Please generate a session string first.")
        return False
    
    try:
        # Create Telethon client with string session
        from telethon.sessions import StringSession
        
        # Clean and validate session string
        session_string = SESSION_STRING.strip()
        if not session_string:
            logger.error("SESSION_STRING is empty")
            return False
            
        userbot_client = TelegramClient(
            StringSession(session_string),
            API_ID,
            API_HASH
        )
        
        await userbot_client.start()
        logger.info("UserBot started successfully!")
        
        # Get user info
        me = await userbot_client.get_me()
        logger.info(f"Logged in as: {me.first_name} (@{me.username})")
        
        # Set up message handler
        @userbot_client.on(events.NewMessage)
        async def handle_new_message(event):
            """Handle incoming messages and forward them"""
            try:
                # Get source chat ID
                source_id = event.chat_id
                
                logger.info(f"📨 New message received from chat ID: {source_id}")
                
                # Check if any task matches this source
                for task in tasks:
                    if not task.get("on", False):
                        continue
                    
                    # Resolve source ID for comparison
                    task_source_id = await resolve_chat_id(userbot_client, task["source"])
                    
                    logger.info(f"🔍 Checking task {task['id']}: {task['source']} (ID: {task_source_id}) -> {task['target']}")
                    logger.info(f"🔍 Comparing source_id: {source_id} with task_source_id: {task_source_id}")
                    
                    # Check if IDs match (handle both positive and negative formats)
                    if (task_source_id == source_id or 
                        task_source_id == abs(source_id) or 
                        abs(task_source_id) == abs(source_id)):
                        # Forward the message
                        target_id = await resolve_chat_id(userbot_client, task["target"])
                        
                        if target_id:
                            try:
                                # Try to get the target entity first
                                target_entity = await userbot_client.get_entity(target_id)
                                await userbot_client.forward_messages(
                                    entity=target_entity,
                                    messages=event.message
                                )
                                logger.info(f"✅ Forwarded message from {task['source']} to {task['target']}")
                            except Exception as forward_error:
                                logger.error(f"❌ Failed to forward message: {forward_error}")
                                # Try alternative forwarding method with direct message
                                try:
                                    message_text = event.message.text or event.message.message or str(event.message)
                                    await userbot_client.send_message(
                                        entity=target_id,
                                        message=f"Forwarded: {message_text}"
                                    )
                                    logger.info(f"✅ Sent message (alternative method) from {task['source']} to {task['target']}")
                                except Exception as alt_error:
                                    logger.error(f"❌ Alternative forwarding also failed: {alt_error}")
                                    # Try with username format if it's a user ID
                                    if str(target_id).isdigit():
                                        try:
                                            await userbot_client.send_message(
                                                entity=int(target_id),
                                                message=f"Forwarded: {message_text}"
                                            )
                                            logger.info(f"✅ Sent message (direct ID method) from {task['source']} to {task['target']}")
                                        except Exception as direct_error:
                                            logger.error(f"❌ Direct ID method also failed: {direct_error}")
                                            logger.error(f"💡 Please ensure the UserBot has interacted with user {target_id} or add them to a mutual group")
                        else:
                            logger.error(f"❌ Could not resolve target: {task['target']}")
                            
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to start UserBot: {e}")
        return False

async def setup_control_bot():
    """Initialize and start the Control Bot"""
    global control_bot
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found. Please provide a valid bot token.")
        return False
    
    try:
        control_bot = Client(
            "control_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN
        )
        
        await control_bot.start()
        logger.info("Control Bot started successfully!")
        
        # Command handlers
        @control_bot.on_message(filters.command("start"))
        async def start_command(client, message: Message):
            """Start command handler"""
            welcome_text = """
🤖 **Welcome to Telegram UserBot Control Panel!**

Here are the available commands:

📝 **Task Management:**
• `/add` - Add a new forwarding task
• `/delete` - Delete an existing task
• `/tasks` - View all tasks

⚡ **Task Control:**
• `/on <task_id>` - Enable a task
• `/off <task_id>` - Disable a task

📊 **Status:**
• `/status` - Check UserBot status

Let's get started! Use `/add` to create your first forwarding task.
            """
            
            # Add inline keyboard buttons
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Add Task", callback_data="add_task")],
                [InlineKeyboardButton("📋 View Tasks", callback_data="view_tasks")],
                [InlineKeyboardButton("📊 Status", callback_data="status")]
            ])
            
            await message.reply_text(welcome_text, reply_markup=keyboard)
        
        @control_bot.on_message(filters.command("add"))
        async def add_task_command(client, message: Message):
            """Add task command handler"""
            try:
                # Get command arguments
                args = message.text.split(maxsplit=2)
                
                if len(args) < 3:
                    await message.reply_text(
                        "📝 **Add Forwarding Task**\n\n"
                        "Usage: `/add <source> <target>`\n\n"
                        "Examples:\n"
                        "• `/add @sourcechannel @targetgroup`\n"
                        "• `/add -1001234567890 @mytarget`\n"
                        "• `/add @mychannel -1001234567890`\n\n"
                        "💡 **Tip:** You can use both @usernames and numeric IDs"
                    )
                    return
                
                source = args[1].strip()
                target = args[2].strip()
                
                # Validate source and target
                if userbot_client:
                    source_id = await resolve_chat_id(userbot_client, source)
                    target_id = await resolve_chat_id(userbot_client, target)
                    
                    if not source_id:
                        await message.reply_text("❌ Invalid source chat. Please check the ID/username.")
                        return
                    
                    if not target_id:
                        await message.reply_text("❌ Invalid target chat. Please check the ID/username.")
                        return
                
                # Add task
                task_id = task_manager.add_task(source, target)
                
                await message.reply_text(
                    f"✅ **Task Added Successfully!**\n\n"
                    f"🆔 Task ID: `{task_id}`\n"
                    f"📥 Source: `{source}`\n"
                    f"📤 Target: `{target}`\n"
                    f"⚡ Status: **ON**\n\n"
                    f"Your task is now active and will forward messages in real-time!"
                )
                
            except Exception as e:
                await message.reply_text(f"❌ Error adding task: {str(e)}")
        
        @control_bot.on_message(filters.command("delete"))
        async def delete_task_command(client, message: Message):
            """Delete task command handler"""
            try:
                args = message.text.split()
                
                if len(args) < 2:
                    if not tasks:
                        await message.reply_text("📭 No tasks found. Use `/add` to create a task first.")
                        return
                    
                    # Show all tasks
                    task_list = "🗂️ **Select a task to delete:**\n\n"
                    for i, task in enumerate(tasks):
                        status = "✅ ON" if task.get("on", False) else "❌ OFF"
                        task_list += f"`{i}` | {task['source']} ➡️ {task['target']} | {status}\n"
                    
                    task_list += "\n💬 Usage: `/delete <task_id>`\nExample: `/delete 0`"
                    
                    await message.reply_text(task_list)
                    return
                
                try:
                    task_id = int(args[1])
                    
                    if task_manager.delete_task(task_id):
                        await message.reply_text(f"🗑️ **Task {task_id} deleted successfully!**")
                    else:
                        await message.reply_text("❌ Invalid task number.")
                        
                except ValueError:
                    await message.reply_text("❌ Please enter a valid number.")
                    
            except Exception as e:
                await message.reply_text(f"❌ Error deleting task: {str(e)}")
        
        @control_bot.on_message(filters.command("tasks"))
        async def list_tasks_command(client, message: Message):
            """List all tasks command handler"""
            try:
                if not tasks:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ Add New Task", callback_data="add_task")]
                    ])
                    await message.reply_text("📭 **No tasks found.**\n\nUse `/add` to create your first forwarding task!", reply_markup=keyboard)
                    return
                
                task_list = "📋 **Your Forwarding Tasks:**\n\n"
                
                buttons = []
                for task in tasks:
                    status = "✅ ON" if task.get("on", False) else "❌ OFF"
                    task_list += f"🆔 `{task['id']}` | {task['source']} ➡️ {task['target']} | {status}\n"
                    
                    # Add buttons for each task
                    if task.get("on", False):
                        buttons.append([InlineKeyboardButton(f"⏸️ Stop Task {task['id']}", callback_data=f"stop_{task['id']}")])
                    else:
                        buttons.append([InlineKeyboardButton(f"▶️ Start Task {task['id']}", callback_data=f"start_{task['id']}")])
                
                task_list += f"\n📊 **Summary:** {len(tasks)} total tasks"
                active_count = len([t for t in tasks if t.get("on", False)])
                task_list += f" | {active_count} active"
                
                # Add control buttons
                buttons.append([InlineKeyboardButton("➕ Add New Task", callback_data="add_task")])
                buttons.append([InlineKeyboardButton("🗑️ Delete Task", callback_data="delete_task")])
                
                keyboard = InlineKeyboardMarkup(buttons)
                await message.reply_text(task_list, reply_markup=keyboard)
                
            except Exception as e:
                await message.reply_text(f"❌ Error listing tasks: {str(e)}")
        
        @control_bot.on_message(filters.command("on"))
        async def enable_task_command(client, message: Message):
            """Enable task command handler"""
            try:
                # Get task ID from command
                args = message.text.split()
                if len(args) < 2:
                    await message.reply_text("❌ Usage: `/on <task_id>`\n\nExample: `/on 0`")
                    return
                
                task_id = int(args[1])
                
                if task_manager.toggle_task(task_id, True):
                    task = task_manager.get_task(task_id)
                    await message.reply_text(
                        f"✅ **Task {task_id} enabled!**\n\n"
                        f"📥 Source: `{task['source']}`\n"
                        f"📤 Target: `{task['target']}`\n"
                        f"⚡ Status: **ON**"
                    )
                else:
                    await message.reply_text("❌ Invalid task ID.")
                    
            except (ValueError, IndexError):
                await message.reply_text("❌ Please provide a valid task ID.")
            except Exception as e:
                await message.reply_text(f"❌ Error enabling task: {str(e)}")
        
        @control_bot.on_message(filters.command("off"))
        async def disable_task_command(client, message: Message):
            """Disable task command handler"""
            try:
                # Get task ID from command
                args = message.text.split()
                if len(args) < 2:
                    await message.reply_text("❌ Usage: `/off <task_id>`\n\nExample: `/off 0`")
                    return
                
                task_id = int(args[1])
                
                if task_manager.toggle_task(task_id, False):
                    task = task_manager.get_task(task_id)
                    await message.reply_text(
                        f"❌ **Task {task_id} disabled!**\n\n"
                        f"📥 Source: `{task['source']}`\n"
                        f"📤 Target: `{task['target']}`\n"
                        f"⚡ Status: **OFF**"
                    )
                else:
                    await message.reply_text("❌ Invalid task ID.")
                    
            except (ValueError, IndexError):
                await message.reply_text("❌ Please provide a valid task ID.")
            except Exception as e:
                await message.reply_text(f"❌ Error disabling task: {str(e)}")
        
        @control_bot.on_message(filters.command("status"))
        async def status_command(client, message: Message):
            """Status command handler"""
            try:
                userbot_status = "🟢 Connected" if userbot_client and userbot_client.is_connected() else "🔴 Disconnected"
                control_bot_status = "🟢 Connected" if control_bot else "🔴 Disconnected"
                
                active_tasks = len([task for task in tasks if task.get("on", False)])
                total_tasks = len(tasks)
                
                status_text = f"""
📊 **System Status**

🤖 **UserBot:** {userbot_status}
🎛️ **Control Bot:** {control_bot_status}

📋 **Tasks:** {active_tasks}/{total_tasks} active
⏰ **Uptime:** Running 24/7

💡 **Tip:** Use `/tasks` to manage your forwarding tasks.
                """
                
                await message.reply_text(status_text)
                
            except Exception as e:
                await message.reply_text(f"❌ Error getting status: {str(e)}")
        
        @control_bot.on_message(filters.command("login"))
        async def login_help_command(client, message: Message):
            """Login help command handler"""
            help_text = """
🔐 **Session String Generation Guide**

To generate a session string:

1️⃣ **Use the helper script:**
   Run `python session_generator.py`

2️⃣ **Manual method:**
   • Install: `pip install telethon`
   • Create a script with your API_ID and API_HASH
   • Use `client.session.save()` to get the string

3️⃣ **Required credentials:**
   • API_ID and API_HASH from https://my.telegram.org
   • Your phone number for verification

⚠️ **Important:** Keep your session string private and secure!

Need help? Check the README.md file for detailed instructions.
            """
            await message.reply_text(help_text)
        
        # Callback query handlers for inline buttons
        @control_bot.on_callback_query()
        async def handle_callback(client, callback_query):
            """Handle inline button callbacks"""
            data = callback_query.data
            
            if data == "add_task":
                await callback_query.message.reply_text(
                    "📝 **Add Forwarding Task**\n\n"
                    "Usage: `/add <source> <target>`\n\n"
                    "Examples:\n"
                    "• `/add @sourcechannel @targetgroup`\n"
                    "• `/add -1001234567890 @mytarget`\n"
                    "• `/add @mychannel -1001234567890`\n\n"
                    "💡 **Tip:** You can use both @usernames and numeric IDs"
                )
            elif data == "view_tasks":
                # Show tasks
                if not tasks:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("➕ Add New Task", callback_data="add_task")]
                    ])
                    await callback_query.message.reply_text("📭 **No tasks found.**\n\nUse `/add` to create your first forwarding task!", reply_markup=keyboard)
                else:
                    task_list = "📋 **Your Forwarding Tasks:**\n\n"
                    buttons = []
                    for task in tasks:
                        status = "✅ ON" if task.get("on", False) else "❌ OFF"
                        task_list += f"🆔 `{task['id']}` | {task['source']} ➡️ {task['target']} | {status}\n"
                        
                        # Add buttons for each task
                        if task.get("on", False):
                            buttons.append([InlineKeyboardButton(f"⏸️ Stop Task {task['id']}", callback_data=f"stop_{task['id']}")])
                        else:
                            buttons.append([InlineKeyboardButton(f"▶️ Start Task {task['id']}", callback_data=f"start_{task['id']}")])
                    
                    task_list += f"\n📊 **Summary:** {len(tasks)} total tasks"
                    active_count = len([t for t in tasks if t.get("on", False)])
                    task_list += f" | {active_count} active"
                    
                    # Add control buttons
                    buttons.append([InlineKeyboardButton("➕ Add New Task", callback_data="add_task")])
                    buttons.append([InlineKeyboardButton("🗑️ Delete Task", callback_data="delete_task")])
                    
                    keyboard = InlineKeyboardMarkup(buttons)
                    await callback_query.message.reply_text(task_list, reply_markup=keyboard)
            elif data == "status":
                # Show status
                userbot_status = "🟢 Connected" if userbot_client and userbot_client.is_connected() else "🔴 Disconnected"
                control_bot_status = "🟢 Connected" if control_bot else "🔴 Disconnected"
                
                active_tasks = len([task for task in tasks if task.get("on", False)])
                total_tasks = len(tasks)
                
                status_text = f"""
📊 **System Status**

🤖 **UserBot:** {userbot_status}
🎛️ **Control Bot:** {control_bot_status}

📋 **Tasks:** {active_tasks}/{total_tasks} active
⏰ **Uptime:** Running 24/7

💡 **Tip:** Use `/tasks` to manage your forwarding tasks.
                """
                
                await callback_query.message.reply_text(status_text)
            elif data.startswith("start_"):
                # Start task
                task_id = int(data.split("_")[1])
                if task_manager.toggle_task(task_id, True):
                    await callback_query.message.reply_text(f"✅ **Task {task_id} started!**")
                else:
                    await callback_query.message.reply_text("❌ Invalid task ID.")
            elif data.startswith("stop_"):
                # Stop task
                task_id = int(data.split("_")[1])
                if task_manager.toggle_task(task_id, False):
                    await callback_query.message.reply_text(f"⏸️ **Task {task_id} stopped!**")
                else:
                    await callback_query.message.reply_text("❌ Invalid task ID.")
            elif data == "delete_task":
                if not tasks:
                    await callback_query.message.reply_text("📭 No tasks to delete.")
                else:
                    buttons = []
                    for task in tasks:
                        buttons.append([InlineKeyboardButton(f"🗑️ Delete Task {task['id']}: {task['source']} → {task['target']}", callback_data=f"del_{task['id']}")])
                    
                    keyboard = InlineKeyboardMarkup(buttons)
                    await callback_query.message.reply_text("🗑️ **Select task to delete:**", reply_markup=keyboard)
            elif data.startswith("del_"):
                # Delete task
                task_id = int(data.split("_")[1])
                if task_manager.delete_task(task_id):
                    await callback_query.message.reply_text(f"🗑️ **Task {task_id} deleted successfully!**")
                else:
                    await callback_query.message.reply_text("❌ Invalid task ID.")
            
            await callback_query.answer()
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to start Control Bot: {e}")
        return False

async def main():
    """Main application entry point"""
    logger.info("Starting Telegram UserBot system...")
    
    # Validate configuration
    if not API_ID or not API_HASH:
        logger.error("API_ID and API_HASH are required. Please check your environment variables.")
        return
    
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is required. Please check your environment variables.")
        return
    
    # Start UserBot (skip if session string is invalid)
    userbot_success = await setup_userbot()
    if not userbot_success:
        logger.error("Failed to start UserBot. Session string may be invalid.")
        logger.info("Control Bot will work without UserBot. Generate a valid session string to enable forwarding.")
    
    # Start Control Bot
    control_success = await setup_control_bot()
    if not control_success:
        logger.error("Failed to start Control Bot. Check your BOT_TOKEN.")
        return
    
    logger.info("🚀 All systems started successfully!")
    logger.info("UserBot is now forwarding messages in real-time")
    logger.info("Control Bot is ready to accept commands")
    
    try:
        # Keep the application running
        if userbot_client:
            await userbot_client.run_until_disconnected()
        else:
            # Keep control bot running if no userbot
            import signal
            def signal_handler(signum, frame):
                logger.info("Received signal to stop")
                raise KeyboardInterrupt
            
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            
            logger.info("Control Bot is running. Press Ctrl+C to stop.")
            await asyncio.Event().wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        # Cleanup
        if userbot_client:
            await userbot_client.disconnect()
        if control_bot:
            await control_bot.stop()

if __name__ == "__main__":
    # Run the application
    asyncio.run(main())
