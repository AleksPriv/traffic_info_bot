Morning Traffic Info Telegram Bot

A Python script designed to run headless on a Raspberry Pi. Every weekday morning, it calculates the optimal route from your home to your workplace using the modern **Google Routes API (v2)**, generates a custom route map with **live color-coded traffic segments** (Green/Orange/Red), and sends a neat summary image directly to your personal Telegram chat.

## Prerequisites
1. **Google Cloud Platform Account:**
   * Enable **Routes API** (v2) and **Maps Static API**.
   * Generate an API Key restricted to these services.
2. **Telegram Bot:**
   * Created via `@BotFather`.
   * Your personal Telegram **Chat ID** (retrieved via `@userinfobot`).

## Setup & Installation
1. **Clone or download this repository** into your local workspace/Raspberry Pi:
2. **Set up a Virtual Environment and install dependencies:**
3. **Configure Environment Variables:**
    Create a hidden .env file in the root of the project directory:
    GOOGLE_MAPS_KEY=your_google_api_key_here
    TELEGRAM_TOKEN=your_telegram_bot_token_here
    TELEGRAM_CHAT_ID=your_personal_chat_id_here
    HOME_ADDRESS=e.g. 123 Main St, Your City, State
    WORK_ADDRESS=e.g. 456 Office Blvd, Business City, State

## Automation (Crontab)
To schedule the script to run automatically every Monday through Friday morning at 7:30 AM, open your system scheduler:
crontab -e

Append the following line at the very bottom (adjust paths for your specific user environment):
30 7 * * 1-5 /home/user/morning-bot/venv/bin/python3 /home/user/morning-bot/traffic_info.py >> /home/user/morning-bot/log.txt 2>&1

## License
This project is open-source and free to adapt for personal automation workflows. Keep your .env private!
