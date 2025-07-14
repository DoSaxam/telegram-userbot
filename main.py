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

# FastAPI for web server
from fastapi import FastAPI, HTTPException
import uvicorn
import threading

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
PORT = int(os.getenv("PORT", "5000"))

# Global variables
userbot_client: Optional[TelegramClient] = None
control_bot: Optional[Client] = None
tasks: List[Dict] = []
forwarding_active = {}

# Web server app
app = FastAPI(title="Telegram UserBot System", version="1.0.0")

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
                    f"🟢 Status: Active\n\n"
                    f"Your UserBot will now forward messages from {source} to {target}!"
                )
                
            except Exception as e:
                logger.error(f"Error in add_task_command: {e}")
                await message.reply_text("❌ Error adding task. Please try again.")
        
        @control_bot.on_message(filters.command("delete"))
        async def delete_task_command(client, message: Message):
            """Delete task command handler"""
            try:
                args = message.text.split()
                
                if len(args) < 2:
                    await message.reply_text(
                        "🗑️ **Delete Task**\n\n"
                        "Usage: `/delete <task_id>`\n\n"
                        "Example: `/delete 0`\n\n"
                        "Use `/tasks` to see all task IDs."
                    )
                    return
                
                task_id = int(args[1])
                
                if task_manager.delete_task(task_id):
                    await message.reply_text(f"✅ Task {task_id} deleted successfully!")
                else:
                    await message.reply_text(f"❌ Task {task_id} not found.")
                    
            except ValueError:
                await message.reply_text("❌ Invalid task ID. Please provide a number.")
            except Exception as e:
                logger.error(f"Error in delete_task_command: {e}")
                await message.reply_text("❌ Error deleting task. Please try again.")
        
        @control_bot.on_message(filters.command("tasks"))
        async def list_tasks_command(client, message: Message):
            """List all tasks command handler"""
            try:
                all_tasks = task_manager.get_all_tasks()
                
                if not all_tasks:
                    await message.reply_text(
                        "📋 **No Tasks Found**\n\n"
                        "You haven't created any forwarding tasks yet.\n"
                        "Use `/add <source> <target>` to create your first task!"
                    )
                    return
                
                tasks_text = "📋 **Your Forwarding Tasks:**\n\n"
                
                for task in all_tasks:
                    status = "🟢 Active" if task.get("on", False) else "🔴 Inactive"
                    tasks_text += (
                        f"**Task {task['id']}:**\n"
                        f"📥 Source: `{task['source']}`\n"
                        f"📤 Target: `{task['target']}`\n"
                        f"Status: {status}\n"
                        f"Created: {task.get('created_at', 'Unknown')[:10]}\n\n"
                    )
                
                tasks_text += (
                    "**Commands:**\n"
                    "• `/on <id>` - Enable task\n"
                    "• `/off <id>` - Disable task\n"
                    "• `/delete <id>` - Delete task"
                )
                
                await message.reply_text(tasks_text)
                
            except Exception as e:
                logger.error(f"Error in list_tasks_command: {e}")
                await message.reply_text("❌ Error listing tasks. Please try again.")
        
        @control_bot.on_message(filters.command("on"))
        async def enable_task_command(client, message: Message):
            """Enable task command handler"""
            try:
                args = message.text.split()
                
                if len(args) < 2:
                    await message.reply_text(
                        "⚡ **Enable Task**\n\n"
                        "Usage: `/on <task_id>`\n\n"
                        "Example: `/on 0`"
                    )
                    return
                
                task_id = int(args[1])
                
                if task_manager.toggle_task(task_id, True):
                    await message.reply_text(f"✅ Task {task_id} enabled successfully!")
                else:
                    await message.reply_text(f"❌ Task {task_id} not found.")
                    
            except ValueError:
                await message.reply_text("❌ Invalid task ID. Please provide a number.")
            except Exception as e:
                logger.error(f"Error in enable_task_command: {e}")
                await message.reply_text("❌ Error enabling task. Please try again.")
        
        @control_bot.on_message(filters.command("off"))
        async def disable_task_command(client, message: Message):
            """Disable task command handler"""
            try:
                args = message.text.split()
                
                if len(args) < 2:
                    await message.reply_text(
                        "⚡ **Disable Task**\n\n"
                        "Usage: `/off <task_id>`\n\n"
                        "Example: `/off 0`"
                    )
                    return
                
                task_id = int(args[1])
                
                if task_manager.toggle_task(task_id, False):
                    await message.reply_text(f"✅ Task {task_id} disabled successfully!")
                else:
                    await message.reply_text(f"❌ Task {task_id} not found.")
                    
            except ValueError:
                await message.reply_text("❌ Invalid task ID. Please provide a number.")
            except Exception as e:
                logger.error(f"Error in disable_task_command: {e}")
                await message.reply_text("❌ Error disabling task. Please try again.")
        
        @control_bot.on_message(filters.command("status"))
        async def status_command(client, message: Message):
            """Status command handler"""
            try:
                userbot_status = "🟢 Online" if userbot_client and userbot_client.is_connected() else "🔴 Offline"
                control_bot_status = "🟢 Online" if control_bot and control_bot.is_connected else "🔴 Offline"
                
                active_tasks = len([task for task in tasks if task.get("on", False)])
                total_tasks = len(tasks)
                
                status_text = (
                    "📊 **System Status**\n\n"
                    f"🤖 UserBot: {userbot_status}\n"
                    f"🎛️ Control Bot: {control_bot_status}\n"
                    f"📋 Active Tasks: {active_tasks}/{total_tasks}\n"
                    f"📅 Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                    "**Quick Actions:**\n"
                    "• `/tasks` - View all tasks\n"
                    "• `/add` - Create new task"
                )
                
                await message.reply_text(status_text)
                
            except Exception as e:
                logger.error(f"Error in status_command: {e}")
                await message.reply_text("❌ Error getting status. Please try again.")
        
        @control_bot.on_message(filters.command("help"))
        async def login_help_command(client, message: Message):
            """Login help command handler"""
            help_text = """
🔧 **Setup Help**

**Getting Your Credentials:**

1️⃣ **API Credentials**
   • Go to https://my.telegram.org/apps
   • Create new application
   • Get API_ID and API_HASH

2️⃣ **Bot Token**
   • Message @BotFather
   • Create bot with /newbot
   • Get BOT_TOKEN

3️⃣ **Session String**
   • Run session_generator.py
   • Enter credentials and phone
   • Get SESSION_STRING

**Common Issues:**
• Invalid session → Generate new session string
• Bot not responding → Check BOT_TOKEN
• Can't forward → Check UserBot permissions

Need more help? Check the documentation!
            """
            await message.reply_text(help_text)
        
        # Callback query handler
        @control_bot.on_callback_query()
        async def handle_callback(client, callback_query):
            """Handle inline button callbacks"""
            try:
                data = callback_query.data
                
                if data == "add_task":
                    await callback_query.message.reply_text(
                        "📝 **Add New Task**\n\n"
                        "Send: `/add <source> <target>`\n\n"
                        "Example: `/add @mychannel @mygroup`"
                    )
                    
                elif data == "view_tasks":
                    all_tasks = task_manager.get_all_tasks()
                    
                    if not all_tasks:
                        await callback_query.message.reply_text(
                            "📋 **No Tasks Found**\n\n"
                            "Create your first task with `/add`"
                        )
                    else:
                        tasks_text = "📋 **Your Tasks:**\n\n"
                        for task in all_tasks:
                            status = "🟢" if task.get("on", False) else "🔴"
                            tasks_text += f"{status} Task {task['id']}: {task['source']} → {task['target']}\n"
                        
                        await callback_query.message.reply_text(tasks_text)
                        
                elif data == "status":
                    userbot_status = "🟢" if userbot_client and userbot_client.is_connected() else "🔴"
                    control_bot_status = "🟢" if control_bot and control_bot.is_connected else "🔴"
                    
                    status_text = (
                        f"📊 **Status**\n\n"
                        f"UserBot: {userbot_status}\n"
                        f"Control Bot: {control_bot_status}\n"
                        f"Tasks: {len([t for t in tasks if t.get('on')])}/{len(tasks)} active"
                    )
                    
                    await callback_query.message.reply_text(status_text)
                
                await callback_query.answer()
                
            except Exception as e:
                logger.error(f"Error in callback handler: {e}")
                await callback_query.answer("❌ Error processing request")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to start Control Bot: {e}")
        return False

# Web endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "status": "running",
        "service": "Telegram UserBot System", 
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "status": "/status"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    userbot_status = userbot_client and userbot_client.is_connected()
    control_bot_status = control_bot and control_bot.is_connected
    
    return {
        "status": "healthy" if (userbot_status or control_bot_status) else "unhealthy",
        "userbot": "connected" if userbot_status else "disconnected",
        "control_bot": "connected" if control_bot_status else "disconnected",
        "tasks": {
            "total": len(tasks),
            "active": len([task for task in tasks if task.get("on", False)])
        },
        "timestamp": datetime.now().isoformat()
    }

@app.get("/status")
async def status():
    """Detailed status endpoint"""
    return {
        "system": {
            "userbot_connected": userbot_client and userbot_client.is_connected(),
            "control_bot_connected": control_bot and control_bot.is_connected,
            "tasks_loaded": len(tasks)
        },
        "tasks": [
            {
                "id": task["id"],
                "source": task["source"],
                "target": task["target"],
                "active": task.get("on", False),
                "created": task.get("created_at")
            }
            for task in tasks
        ],
        "environment": {
            "api_id_set": bool(API_ID),
            "api_hash_set": bool(API_HASH),
            "bot_token_set": bool(BOT_TOKEN),
            "session_string_set": bool(SESSION_STRING)
        }
    }

def run_web_server():
    """Run the web server in a separate thread"""
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")

async def main():
    """Main application entry point"""
    import signal
    
    logger.info("Starting Telegram UserBot System...")
    
    # Start web server in background thread
    web_thread = threading.Thread(target=run_web_server, daemon=True)
    web_thread.start()
    logger.info(f"Web server started on port {PORT}")
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal, stopping...")
        if userbot_client:
            asyncio.create_task(userbot_client.disconnect())
        if control_bot:
            asyncio.create_task(control_bot.stop())
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Check configuration
    if not API_ID or not API_HASH:
        logger.error("API_ID and API_HASH are required!")
        return
    
    # Start bots
    userbot_started = False
    control_bot_started = False
    
    if SESSION_STRING:
        userbot_started = await setup_userbot()
    else:
        logger.warning("SESSION_STRING not provided. UserBot will not start.")
    
    if BOT_TOKEN:
        control_bot_started = await setup_control_bot()
    else:
        logger.warning("BOT_TOKEN not provided. Control Bot will not start.")
    
    if not userbot_started and not control_bot_started:
        logger.error("Neither UserBot nor Control Bot could be started. Check your credentials.")
        return
    
    logger.info("System started successfully! Web server is running.")
    
    # Keep the application running
    try:
        if userbot_client:
            await userbot_client.run_until_disconnected()
        elif control_bot:
            await control_bot.idle()
        else:
            # If neither bot is running, just keep the web server alive
            while True:
                await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        if userbot_client:
            await userbot_client.disconnect()
        if control_bot:
            await control_bot.stop()

if __name__ == "__main__":
    asyncio.run(main())