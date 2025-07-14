# Telegram UserBot System

## Overview

A production-ready Telegram UserBot system that enables real-time message forwarding between channels and chats. The system features a dual-bot architecture with a UserBot for forwarding messages and a Control Bot for managing tasks through simple Telegram commands. It's designed for 24/7 deployment on cloud platforms like Render.com and Replit.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Dual-Bot Architecture
The system uses two separate Telegram clients working together:
- **UserBot (Telethon)**: Handles the actual message forwarding operations
- **Control Bot (Pyrogram)**: Provides a user-friendly interface for managing forwarding tasks

This separation allows for better security, reliability, and user experience. The UserBot operates with user credentials while the Control Bot uses a standard bot token.

### Backend Architecture
- **Asynchronous Processing**: Built on asyncio for handling multiple concurrent operations
- **JSON-Based Storage**: Simple file-based persistence for task management
- **In-Memory Task Tracking**: Active forwarding tasks are tracked in memory for performance
- **Logging System**: Comprehensive logging to both file and console for debugging

## Key Components

### 1. UserBot Client (Telethon)
**Purpose**: Handles real-time message forwarding between chats/channels
- Authenticates using session string (no password required after setup)
- Monitors source channels for new messages
- Forwards messages to target destinations
- Supports both private chats and channels

### 2. Control Bot (Pyrogram) 
**Purpose**: Provides command interface for task management
- Standard bot authentication using bot token
- Inline keyboard interface for easy interaction
- Commands for creating, managing, and monitoring forwarding tasks
- Real-time status updates and notifications

### 3. Task Management System
**Purpose**: Handles storage and lifecycle of forwarding tasks
- JSON file persistence (`tasks.json`)
- Unique task IDs for tracking
- Start/stop functionality for individual tasks
- Task status monitoring and reporting

### 4. Session Generator Utility
**Purpose**: Simplifies initial setup by generating session strings
- Guides users through Telegram authentication
- Generates reusable session strings
- Eliminates need for repeated login prompts

## Data Flow

### Message Forwarding Flow
1. UserBot monitors configured source channels/chats
2. When new message detected, UserBot immediately forwards to target
3. Control Bot provides real-time status updates to user
4. All activities are logged for monitoring and debugging

### Task Management Flow
1. User sends commands to Control Bot
2. Control Bot validates requests and updates task storage
3. Task Manager loads/saves tasks to JSON file
4. UserBot receives task updates and adjusts monitoring
5. Status updates are sent back to user through Control Bot

## External Dependencies

### Required Telegram Credentials
- **API_ID & API_HASH**: From my.telegram.org for Telethon client
- **BOT_TOKEN**: From @BotFather for Control Bot
- **SESSION_STRING**: Generated via session_generator.py for UserBot

### Python Libraries
- **Telethon**: Primary library for UserBot functionality and session management
- **Pyrogram**: Control Bot operations and inline keyboards
- **FastAPI**: Web server for health checks and cloud deployment compatibility
- **Asyncio**: Built-in library for concurrent operations

### Platform Requirements
- Python 3.8+ runtime environment
- Persistent file storage for tasks.json
- Network access to Telegram servers
- Environment variable support for credentials

## Deployment Strategy

### Cloud Platform Compatibility
- **Render.com**: Configured with Dockerfile and render.yaml
- **Replit.com**: Uses replit.nix for environment setup
- **Generic Platforms**: Standard Python requirements.txt

### Environment Configuration
- Credentials stored as environment variables or platform secrets
- No hardcoded sensitive information
- Graceful fallbacks for missing configuration

### Health Monitoring
- FastAPI endpoints for platform health checks
- Comprehensive logging for debugging issues
- Automatic task persistence for recovery after restarts

### Security Considerations
- Session strings used instead of passwords for UserBot
- Control Bot token separate from UserBot credentials
- No sensitive data in code repository
- JSON task storage without credential exposure

The system is designed to be beginner-friendly while maintaining production-grade reliability and security. The dual-bot architecture ensures that forwarding operations continue even if the control interface needs maintenance, and the simple JSON storage makes the system easy to understand and modify.