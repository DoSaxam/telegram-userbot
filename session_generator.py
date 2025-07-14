#!/usr/bin/env python3
"""
Session String Generator for Telegram UserBot
This script helps generate session strings for Telethon UserBot authentication.
"""

import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession

def get_credentials():
    """Get API credentials from user"""
    print("🔑 Telegram UserBot Session Generator")
    print("=" * 50)
    print()
    
    # Get API credentials
    api_id = input("Enter your API_ID (from my.telegram.org): ").strip()
    api_hash = input("Enter your API_HASH (from my.telegram.org): ").strip()
    
    if not api_id or not api_hash:
        print("❌ API_ID and API_HASH are required!")
        return None, None
    
    try:
        api_id = int(api_id)
    except ValueError:
        print("❌ API_ID must be a number!")
        return None, None
    
    return api_id, api_hash

async def generate_session():
    """Generate session string"""
    print("\n📱 Starting session generation...")
    
    # Get credentials
    api_id, api_hash = get_credentials()
    if not api_id or not api_hash:
        return
    
    # Create client with string session
    client = TelegramClient(StringSession(), api_id, api_hash)
    
    try:
        # Start client
        await client.start()
        
        # Get user info
        me = await client.get_me()
        print(f"\n✅ Successfully logged in as: {me.first_name}")
        if me.username:
            print(f"   Username: @{me.username}")
        
        # Generate session string
        session_string = client.session.save()
        
        print("\n🎉 Session string generated successfully!")
        print("=" * 50)
        print("📋 Your SESSION_STRING:")
        print(session_string)
        print("=" * 50)
        
        print("\n💡 Next steps:")
        print("1. Copy the session string above")
        print("2. Add it to your environment variables as SESSION_STRING")
        print("3. For Render deployment, add it in the dashboard")
        print("4. For local testing, add it to your .env file")
        
        print("\n⚠️  Important:")
        print("• Keep this session string secure and private")
        print("• Don't share it with anyone")
        print("• This string allows access to your Telegram account")
        
    except Exception as e:
        print(f"\n❌ Error generating session: {e}")
        print("\nTroubleshooting:")
        print("• Check your API_ID and API_HASH")
        print("• Ensure you have internet connection")
        print("• Try again if there was a network error")
    
    finally:
        await client.disconnect()

def main():
    """Main function"""
    print("🚀 Telegram UserBot Session Generator")
    print("   This tool helps you generate session strings for deployment")
    print()
    
    # Check if running in environment with display
    try:
        asyncio.run(generate_session())
    except KeyboardInterrupt:
        print("\n\n⏹️  Session generation cancelled by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")

if __name__ == "__main__":
    main()