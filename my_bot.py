import os
import asyncio
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

# Load environment variables
load_dotenv()

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Initialize GitHub AI client
client = None
if GITHUB_TOKEN:
    endpoint = "https://models.github.ai/inference"
    client = ChatCompletionsClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(GITHUB_TOKEN),
    )
else:
    print("Error: GITHUB_TOKEN not found. Please add it to your .env file.")
    

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Hey! I'm a concise AI assistant. Send me any message and I'll respond briefly."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Commands:\n/start - Start the bot\n/help - Show this help\n\nJust send me any text message and I'll respond!"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages"""
    if not client:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, AI is unavailable right now."
        )
        return

    user_message = update.message.text

    try:
        # Send typing indicator
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        # Get AI response
        response = await asyncio.to_thread(
            client.complete,
            messages=[
                SystemMessage("You are a very concise assistant. Give brief, direct answers in 1-2 sentences max. Be helpful but not conversational."),
                UserMessage(user_message)
            ],
            model="openai/gpt-4.1-nano",
            # model="openai/gpt-5-nano", # not available
            temperature=0.7
        )

        ai_response = response.choices[0].message.content

        # Send response
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=ai_response
        )

    except Exception as e:
        print(f"Error: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, something went wrong. Try again."
        )


def main():
    """Main function to run the bot"""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found. Please add it to your .env file.")
        return
    
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN not found. Please add it to your .env file.")
        return

    # Create application
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is starting...")
    print("Press Ctrl+C to stop the bot")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()