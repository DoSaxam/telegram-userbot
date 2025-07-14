# Render Deployment Guide for Telegram UserBot

## Prerequisites

1. **GitHub Repository**: Push your code to a GitHub repository
2. **Render Account**: Sign up at [render.com](https://render.com)
3. **Telegram Credentials**: Have your API_ID, API_HASH, BOT_TOKEN, and SESSION_STRING ready

## Deployment Steps

### Step 1: Prepare Your Repository

1. Ensure all files are in your GitHub repository:
   - `main.py` (your existing working code)
   - `Dockerfile`
   - `requirements.txt`
   - `render.yaml`
   - `.dockerignore`

2. Push to GitHub:
   ```bash
   git add .
   git commit -m "Add Docker deployment files"
   git push origin main
   ```

### Step 2: Create Render Service

1. **Login to Render Dashboard**
   - Go to https://dashboard.render.com
   - Connect your GitHub account

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select your userbot repository

3. **Configure Service Settings**
   - **Name**: `telegram-userbot` (or your preferred name)
   - **Runtime**: Docker
   - **Region**: Choose closest to your users
   - **Branch**: `main`
   - **Dockerfile Path**: `./Dockerfile`

### Step 3: Set Environment Variables

In the Render dashboard, add these environment variables:

| Variable Name | Value | Description |
|---------------|--------|-------------|
| `API_ID` | Your Telegram API ID | From my.telegram.org |
| `API_HASH` | Your Telegram API Hash | From my.telegram.org |
| `BOT_TOKEN` | Your Bot Token | From @BotFather |
| `SESSION_STRING` | Your Session String | Generated with session_generator.py |
| `PORT` | `5000` | Application port |

**Important**: Mark all credential variables as "Secret" in Render.

### Step 4: Deploy

1. **Start Deployment**
   - Click "Create Web Service"
   - Render will automatically build and deploy your Docker container

2. **Monitor Deployment**
   - Check the "Logs" tab for build progress
   - Look for "UserBot started successfully!" message
   - Verify "Control Bot started successfully!" message

3. **Verify Deployment**
   - Your service will be available at `https://your-service-name.onrender.com`
   - Test health endpoint: `https://your-service-name.onrender.com/health`

### Step 5: Test Your Bot

1. **Check Bot Status**
   - Message your control bot on Telegram
   - Send `/start` command
   - Verify you get the welcome message

2. **Test Forwarding**
   - Create a test forwarding task: `/add @source @target`
   - Send a message to the source
   - Verify it forwards to the target

## Important Notes

### 24/7 Operation
- Render keeps your service running 24/7
- Auto-restarts if the service crashes
- Health checks ensure availability

### Data Persistence
- Tasks are stored in `tasks.json`
- Render provides persistent disk storage
- Your tasks will survive restarts

### Monitoring
- Check logs in Render dashboard
- Health endpoint: `/health`
- Status endpoint: `/status`

### Scaling
- Start with "Starter" plan ($7/month)
- Upgrade to "Standard" for better performance
- No code changes needed for scaling

## Troubleshooting

### Common Issues

1. **Build Fails**
   ```
   Solution: Check Dockerfile syntax and requirements.txt
   ```

2. **Service Starts but Bots Don't Work**
   ```
   Solution: Verify environment variables are set correctly
   Check logs for authentication errors
   ```

3. **Session String Invalid**
   ```
   Solution: Generate new session string with session_generator.py
   Update SESSION_STRING environment variable
   ```

4. **Port Issues**
   ```
   Solution: Ensure PORT=5000 in environment variables
   Verify main.py binds to 0.0.0.0:5000
   ```

### Getting Logs

1. **Real-time Logs**
   - Go to Render Dashboard → Your Service → Logs
   - Monitor live application logs

2. **Download Logs**
   - Use Render CLI or dashboard export feature

### Updating Your Bot

1. **Code Changes**
   - Push changes to GitHub
   - Render auto-deploys from main branch

2. **Environment Variables**
   - Update in Render dashboard
   - Service restarts automatically

## Support

- **Render Documentation**: https://render.com/docs
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Health Check**: Visit your service URL + `/health`

Your Telegram UserBot is now deployed and running 24/7 on Render! 🚀
