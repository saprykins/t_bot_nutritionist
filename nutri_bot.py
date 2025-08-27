import os
import asyncio
import csv
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler
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
    try:
        client = ChatCompletionsClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(GITHUB_TOKEN),
        )
    except Exception as e:
        print(f"Error initializing AI client: {e}")
        client = None
else:
    print("Warning: GITHUB_TOKEN not found. AI functionality will be limited.")


# Define the CSV file name and headers, now including calories
CSV_FILE_NAME = "user_data.csv"
CSV_HEADERS = ["chat_id", "sex", "weight", "height", "age", "activity", "goal", "calories"]

# Define activity multipliers for calorie calculation
ACTIVITY_MULTIPLIERS = {
    "minimum": 1.2,
    "low": 1.375,
    "medium": 1.55,
    "hard": 1.725,
    "extremely high": 1.9
}


def initialize_csv():
    """Creates a CSV file with headers if it doesn't exist."""
    if not os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, "w", newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(CSV_HEADERS)
        print(f"Created new CSV file: {CSV_FILE_NAME}")

def store_user_data(user_data: dict):
    """Appends a new row of user data to the CSV file."""
    with open(CSV_FILE_NAME, "a", newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([user_data.get(header) for header in CSV_HEADERS])
    print(f"Stored data for chat_id: {user_data.get('chat_id')}")

def get_latest_user_data(chat_id: int):
    """
    Retrieves the last saved user data from the CSV.
    Returns a dictionary with data or None if no data is found or if data is incomplete.
    """
    user_data = None
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, "r", newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reversed(list(reader)):
                if int(row["chat_id"]) == chat_id:
                    # Check if all required keys exist to prevent KeyError
                    if all(key in row for key in ['weight', 'height', 'age', 'sex', 'activity', 'goal']):
                        try:
                            # Convert string values to correct types
                            row['weight'] = float(row['weight'])
                            row['height'] = float(row['height'])
                            row['age'] = int(row['age'])
                            row['calories'] = float(row['calories']) if row['calories'] else None
                            user_data = row
                            break # Found the latest complete entry, exit loop
                        except (ValueError, KeyError) as e:
                            # Log error and continue to the next row in case of bad data
                            print(f"Skipping incomplete or corrupt row for chat_id {chat_id}: {e}")
                            continue
    return user_data


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command and displays the main menu."""
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="welcome"
    )
    # Wait for 1 second before sending the main menu
    await asyncio.sleep(1)

    keyboard = [
        [
            InlineKeyboardButton("Fill in", callback_data="fill_in"),
            InlineKeyboardButton("Generate menu", callback_data="generate_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="here's main menu:\n1/ insert your data and get calory estimation\n2/ generate a menu",
        reply_markup=reply_markup
    )
    # Initialize the state for user data collection
    context.user_data['state'] = None


async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks from the main menu."""
    query = update.callback_query
    await query.answer()

    if query.data == "generate_menu":
        user_data = get_latest_user_data(update.effective_chat.id)
        if not user_data:
            await query.edit_message_text(text="Please fill in your data first by clicking 'Fill in' button.")
            return

        # Prepare the message with user data for confirmation
        message_text = (
            f"Request menu for a person with the following:\n"
            f"sex: {user_data['sex'].capitalize()}\n"
            f"age: {user_data['age']}\n"
            f"weight: {user_data['weight']} kg\n"
            f"height: {user_data['height']} cm\n"
            f"activity: {user_data['activity'].capitalize()}\n"
            f"goal: {user_data['goal'].capitalize()}\n"
            f"\nClick on the button below to generate a week menu"
        )
        
        keyboard = [[InlineKeyboardButton("Generate a week menu", callback_data="generate_menu_confirmed")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(text=message_text, reply_markup=reply_markup)

    elif query.data == "fill_in":
        await query.edit_message_text(text="fill in information")

        # Set the state to the next step
        context.user_data['state'] = 'awaiting_sex'
        # Store chat ID for CSV
        context.user_data['chat_id'] = update.effective_chat.id
        
        keyboard = [
            [
                InlineKeyboardButton("Man", callback_data="man"),
                InlineKeyboardButton("Woman", callback_data="woman")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="choose your sex, there're 2 options man, woman",
            reply_markup=reply_markup
        )


async def sex_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles sex choice and asks for weight."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['sex'] = query.data
    context.user_data['state'] = 'awaiting_weight'
    
    await query.edit_message_text(text=f"You chose: {query.data.capitalize()}\n\nPlease specify your weight (e.g., 70.5)")


async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles user's text input based on the current state."""
    state = context.user_data.get('state')
    user_input = update.message.text
    
    if state == 'awaiting_weight':
        try:
            weight = float(user_input)
            context.user_data['weight'] = weight
            context.user_data['state'] = 'awaiting_height'
            await update.message.reply_text("Now, please specify your height in cm (e.g., 175.0)")
        except ValueError:
            await update.message.reply_text("Invalid input. Please enter a valid number for your weight.")
            
    elif state == 'awaiting_height':
        try:
            height = float(user_input)
            context.user_data['height'] = height
            context.user_data['state'] = 'awaiting_age'
            await update.message.reply_text("And your age in years, please.")
        except ValueError:
            await update.message.reply_text("Invalid input. Please enter a valid number for your height.")

    elif state == 'awaiting_age':
        try:
            age = int(user_input)
            context.user_data['age'] = age
            context.user_data['state'] = 'awaiting_activity'
            
            activity_options = [
                ["minimum", "low"],
                ["medium", "hard"],
                ["extremely high"]
            ]
            
            keyboard = [[InlineKeyboardButton(text, callback_data=f"activity_{text.replace(' ', '_')}") for text in row] for row in activity_options]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "Now, please specify your activity level:\n"
                "minimum: little to no exercise\n"
                "low: light exercise/sports 1-3 days/week\n"
                "medium: moderate exercise/sports 3-5 days/week\n"
                "hard: hard exercise/sports 6-7 days a week\n"
                "extremely high: very hard exercise/physical job or training twice a day",
                reply_markup=reply_markup
            )
        except ValueError:
            await update.message.reply_text("Invalid input. Please enter a valid number for your age.")

    # All other messages are ignored as they are not part of the data collection flow
    else:
        await update.message.reply_text("Please use the menu to start data entry. Use /start if you want to see the main menu.")


async def activity_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles activity level choice and asks for goal."""
    query = update.callback_query
    await query.answer()
    
    activity = query.data.replace("activity_", "").replace("_", " ")
    context.user_data['activity'] = activity
    context.user_data['state'] = 'awaiting_goal'
    
    goal_options = ["keep as it is", "lost weight", "take weight"]
    keyboard = [[InlineKeyboardButton(text, callback_data=f"goal_{text.replace(' ', '_')}") for text in goal_options]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text=f"You chose: {activity.capitalize()}\n\nWhat is your goal?", reply_markup=reply_markup)


async def goal_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles goal choice and offers to calculate calories."""
    query = update.callback_query
    await query.answer()
    
    goal = query.data.replace("goal_", "").replace("_", " ")
    context.user_data['goal'] = goal
    
    # Reset the state and present the final option
    context.user_data['state'] = None

    keyboard = [[InlineKeyboardButton("Calculate", callback_data="calculate_calories")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=f"You chose: {goal.capitalize()}\n\nThank you! The form is filled in. Would you like to calculate your daily calorie norm?",
        reply_markup=reply_markup
    )


async def calculate_calories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculates and displays the daily calorie norm."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(text="We'll calculate your needed calories.")

    user_data = context.user_data
    sex = user_data.get('sex')
    weight = user_data.get('weight')
    height = user_data.get('height')
    age = user_data.get('age')
    activity = user_data.get('activity')

    # Calculate Basal Metabolic Rate (BMR)
    if sex == 'man':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else: # 'woman'
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    # Calculate daily calories based on activity level
    activity_multiplier = ACTIVITY_MULTIPLIERS.get(activity, 1.2)
    daily_calories = bmr * activity_multiplier

    # Save the final, complete user data to the CSV file
    user_data['calories'] = round(daily_calories, 2)
    store_user_data(user_data)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"Your daily norm is {round(daily_calories, 0)} calories."
    )
    
    # Present the main menu again after calculation
    keyboard = [
        [
            InlineKeyboardButton("Fill in", callback_data="fill_in"),
            InlineKeyboardButton("Generate menu", callback_data="generate_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="What's next? You can update your data or generate a menu.",
        reply_markup=reply_markup
    )


async def generate_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a weekly menu using GitHub AI."""
    query = update.callback_query
    await query.answer()

    if not client:
        await query.edit_message_text(text="Sorry, AI is unavailable right now.")
        return

    # Get the latest user data from CSV
    user_data = get_latest_user_data(update.effective_chat.id)
    if not user_data:
        await query.edit_message_text(text="Sorry, I could not find your data. Please fill in the form again.")
        return

    # Send a "typing" indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    system_prompt = (
        "You are a professional nutritionist with extensive experience in creating personalized meal plans."
        "Your task is to create a 7-day menu based on user input (gender, age, height, weight, physical activity level, and goal—weight loss, weight maintenance, or muscle gain)."
        "The menu should include a calculation of daily macronutrients (protein, fats, and carbohydrates) and calories."
        "Requirements for the response:\n"
        "Take individual parameters into account when calculating daily calorie, protein, fat, and carbohydrate needs."
        "Make the diet balanced: include different sources of protein, complex carbohydrates, healthy fats, vegetables, and fruits."
        "For each day, specify:"
        "Total calories (kcal)"
        "Protein / Fats / Carbohydrates (in grams)"
        "A detailed menu (breakfast, snack, lunch, snack, dinner—with a list of dishes and approximate portion sizes)."
        "The menu should be practical and realistic for home cooking."
        "The writing style should be clear, structured, and concise."
        "Always structure the response by day:"
        "Day 1\n"
        "Calories: ...\n"
        "Macronutrients (P/F/C): ...\n"
        "Breakfast: ...\n"
        "Snack: ...\n"
        "Lunch: ...\n"
        "Snack: ...\n"
        "Dinner: ...\n"
        "Don't duplicate dishes too often; ensure variety throughout the week."
        "If the goal is 'weight loss,' include a moderate calorie deficit. If the goal is 'muscle gain,' include a calorie surplus."
    )

    user_message = (
        f"Input data:\n"
        f"Gender: {user_data.get('sex')}\n"
        f"Age: {user_data.get('age')}\n"
        f"Height: {user_data.get('height')}\n"
        f"Weight: {user_data.get('weight')}\n"
        f"Activity Level: {user_data.get('activity')}\n"
        f"Goal: {user_data.get('goal')}"
    )

    try:
        response = await asyncio.to_thread(
            client.complete,
            messages=[
                SystemMessage(system_prompt),
                UserMessage(user_message)
            ],
            model="openai/gpt-4.1-nano",
            temperature=0.7
        )

        ai_response = response.choices[0].message.content

        # Send the response
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=ai_response
        )

    except Exception as e:
        print(f"Error: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, something went wrong while generating the menu. Try again."
        )


def main():
    """Main function to run the bot."""
    if not BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN not found. Please add it to your .env file.")
        return
    
    initialize_csv()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler('start', start_command))
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^(fill_in|generate_menu)$'))
    application.add_handler(CallbackQueryHandler(sex_choice_callback, pattern='^(man|woman)$'))
    application.add_handler(CallbackQueryHandler(activity_choice_callback, pattern='^activity_'))
    application.add_handler(CallbackQueryHandler(goal_choice_callback, pattern='^goal_'))
    application.add_handler(CallbackQueryHandler(calculate_calories_callback, pattern='^calculate_calories$'))
    application.add_handler(CallbackQueryHandler(generate_menu_callback, pattern='^generate_menu_confirmed$'))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_input))
    
    print("Bot is starting...")
    print("Press Ctrl+C to stop the bot")
    
    # Run the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
