import os
import asyncio
import csv
import json
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    CallbackQueryHandler,
)
from telegram.error import NetworkError
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

# Define the CSV file name and headers
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
    """Retrieves the last saved user data from the CSV."""
    user_data = None
    if os.path.exists(CSV_FILE_NAME):
        with open(CSV_FILE_NAME, "r", newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reversed(list(reader)):
                if int(row["chat_id"]) == chat_id:
                    if all(key in row for key in ['weight', 'height', 'age', 'sex', 'activity', 'goal']):
                        try:
                            row['weight'] = float(row['weight'])
                            row['height'] = float(row['height'])
                            row['age'] = int(row['age'])
                            row['calories'] = float(row['calories']) if row['calories'] else None
                            user_data = row
                            break
                        except (ValueError, KeyError) as e:
                            print(f"Skipping incomplete or corrupt row for chat_id {chat_id}: {e}")
                            continue
    return user_data

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, message: str = "What would you like to do? 🤔"):
    """Helper function to send the main menu."""
    keyboard = [
        [
            InlineKeyboardButton("📝 My Profile", callback_data="fill_in"),
            InlineKeyboardButton("🗓️ Generate Menu", callback_data="generate_menu")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Clear any ongoing state
    context.user_data['state'] = None
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=message,
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message,
            reply_markup=reply_markup
        )

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command and displays the main menu."""
    welcome_message = (
        "🥗 Welcome to your Personal Nutrition Assistant! 👋\n\n"
        "I'm here to help you:\n"
        "• Calculate your daily calorie needs\n"
        "• Create personalized meal plans\n"
        "• Track your nutrition goals\n\n"
        "Let's start your healthy journey!"
    )
    
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=welcome_message
    )
    
    await asyncio.sleep(1.5)
    await send_main_menu(update, context, "What would you like to do first? 🌟")

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button clicks from the main menu."""
    query = update.callback_query
    await query.answer()

    if query.data == "generate_menu":
        user_data = get_latest_user_data(update.effective_chat.id)
        if not user_data:
            await query.edit_message_text(
                text="🚫 Oops! I need your profile information first.\n\n"
                     "Don't worry, it only takes a minute to set up! 😊"
            )
            
            keyboard = [[InlineKeyboardButton("📝 Create My Profile", callback_data="fill_in")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="Ready to get started? Let's create your profile! 🚀",
                reply_markup=reply_markup
            )
            return

        # Show confirmation with user data
        confirmation_message = (
            f"🎯 Perfect! I'll create your meal plan using:\n\n"
            f"👤 **{user_data['sex'].capitalize()}**, {int(user_data['age'])} years old\n"
            f"⚖️ Weight: **{int(user_data['weight'])} kg**\n"
            f"📏 Height: **{int(user_data['height'])} cm**\n"
            f"🏃 Activity: **{user_data['activity'].capitalize()}**\n"
            f"🎯 Goal: **{user_data['goal'].capitalize()}**\n\n"
            f"Ready for your personalized 7-day meal plan? 🍽️"
        )
        
        keyboard = [
            [InlineKeyboardButton("🥗 Generate My Menu", callback_data="generate_menu_confirmed")],
            [InlineKeyboardButton("📝 Update Profile", callback_data="fill_in")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            text=confirmation_message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

    elif query.data == "fill_in":
        await start_profile_flow(update, context)

async def start_profile_flow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the profile creation/update flow."""
    query = update.callback_query
    user_data = get_latest_user_data(update.effective_chat.id)
    
    if user_data:
        # Show existing data and ask what to do
        profile_summary = (
            f"📋 **Your Current Profile:**\n\n"
            f"👤 {user_data['sex'].capitalize()}, {int(user_data['age'])} years old\n"
            f"⚖️ {int(user_data['weight'])} kg, 📏 {int(user_data['height'])} cm\n"
            f"🏃 Activity: {user_data['activity'].capitalize()}\n"
            f"🎯 Goal: {user_data['goal'].capitalize()}\n\n"
            f"What would you like to do? 🤔"
        )
        
        keyboard = [
            [InlineKeyboardButton("✅ Use Current Profile", callback_data="use_existing_data")],
            [InlineKeyboardButton("🔄 Update Profile", callback_data="start_new_profile")],
            [InlineKeyboardButton("🏠 Back to Menu", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            text=profile_summary,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    else:
        await start_new_profile(update, context)

async def start_new_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Starts the profile creation process."""
    query = update.callback_query
    
    welcome_text = (
        "👋 Let's create your personalized profile!\n\n"
        "I'll ask you a few quick questions to calculate your daily calorie needs "
        "and create the perfect meal plan for you.\n\n"
        "First question: What's your biological sex? 🙋"
    )
    
    keyboard = [
        [
            InlineKeyboardButton("👨 Male", callback_data="sex_male"),
            InlineKeyboardButton("👩 Female", callback_data="sex_female")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    context.user_data['state'] = 'awaiting_sex'
    context.user_data['chat_id'] = update.effective_chat.id
    context.user_data['profile_data'] = {}
    
    await query.edit_message_text(
        text=welcome_text,
        reply_markup=reply_markup
    )

async def sex_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles sex selection."""
    query = update.callback_query
    await query.answer("✅ Got it!")
    
    sex = "man" if query.data == "sex_male" else "woman"
    context.user_data['profile_data']['sex'] = sex
    context.user_data['state'] = 'awaiting_weight'
    
    weight_text = (
        f"✅ Perfect! Now, what's your current weight?\n\n"
        f"💡 **Tip:** Be honest - this helps me create the best plan for you!\n\n"
        f"Please type your weight in kilograms (e.g., **70**)"
    )
    
    await query.edit_message_text(
        text=weight_text,
        parse_mode='Markdown'
    )

async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles user text input based on current state."""
    state = context.user_data.get('state')
    user_input = update.message.text.strip()
    
    if state == 'awaiting_weight':
        await handle_weight_input(update, context, user_input)
    elif state == 'awaiting_height':
        await handle_height_input(update, context, user_input)
    elif state == 'awaiting_age':
        await handle_age_input(update, context, user_input)
    else:
        # User sent a message outside of the expected flow
        await update.message.reply_text(
            "🤔 I'm not sure what you mean right now.\n\n"
            "Use the buttons in our conversation above, or type /start to begin again! 😊"
        )

async def handle_weight_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input: str):
    """Handles weight input validation and processing."""
    try:
        weight = float(user_input)
        if weight <= 0 or weight > 500:  # Basic validation
            await update.message.reply_text(
                "🤔 That doesn't seem right. Please enter a realistic weight in kg (e.g., 70)"
            )
            return
            
        context.user_data['profile_data']['weight'] = weight
        context.user_data['state'] = 'awaiting_height'
        
        height_text = (
            f"📏 Great! Your weight: **{int(weight)} kg**\n\n"
            f"Now, what's your height in centimeters?\n\n"
            f"Please type your height (e.g., **175**)"
        )
        
        await update.message.reply_text(
            text=height_text,
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid number for your weight (e.g., 70)"
        )

async def handle_height_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input: str):
    """Handles height input validation and processing."""
    try:
        height = float(user_input)
        if height <= 0 or height > 250:  # Basic validation
            await update.message.reply_text(
                "🤔 That doesn't seem right. Please enter a realistic height in cm (e.g., 175)"
            )
            return
            
        context.user_data['profile_data']['height'] = height
        context.user_data['state'] = 'awaiting_age'
        
        age_text = (
            f"📏 Perfect! Height: **{int(height)} cm**\n\n"
            f"Almost done! How old are you?\n\n"
            f"Please type your age (e.g., **25**)"
        )
        
        await update.message.reply_text(
            text=age_text,
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid number for your height (e.g., 175)"
        )

async def handle_age_input(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input: str):
    """Handles age input validation and processing."""
    try:
        age = int(user_input)
        if age <= 0 or age > 120:  # Basic validation
            await update.message.reply_text(
                "🤔 Please enter a realistic age (e.g., 25)"
            )
            return
            
        context.user_data['profile_data']['age'] = age
        context.user_data['state'] = 'awaiting_activity'
        
        activity_text = (
            f"🎂 Awesome! Age: **{age} years**\n\n"
            f"Now, tell me about your activity level 💪\n\n"
            f"Choose what best describes your weekly routine:"
        )
        
        keyboard = [
            [InlineKeyboardButton("😴 Minimal (desk job, no exercise)", callback_data="activity_minimum")],
            [InlineKeyboardButton("🚶 Light (1-3 days/week exercise)", callback_data="activity_low")],
            [InlineKeyboardButton("🏃 Moderate (3-5 days/week)", callback_data="activity_medium")],
            [InlineKeyboardButton("💪 High (6-7 days/week)", callback_data="activity_hard")],
            [InlineKeyboardButton("🔥 Extreme (2x daily/physical job)", callback_data="activity_extremely_high")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            text=activity_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid number for your age (e.g., 25)"
        )

async def activity_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles activity level selection."""
    query = update.callback_query
    await query.answer("✅ Activity level noted!")
    
    activity_mapping = {
        "activity_minimum": "minimum",
        "activity_low": "low", 
        "activity_medium": "medium",
        "activity_hard": "hard",
        "activity_extremely_high": "extremely high"
    }
    
    activity = activity_mapping[query.data]
    context.user_data['profile_data']['activity'] = activity
    context.user_data['state'] = 'awaiting_goal'
    
    goal_text = (
        f"💪 Activity level: **{activity.capitalize()}**\n\n"
        f"Last question! What's your main goal? 🎯\n\n"
        f"Choose what you want to achieve:"
    )
    
    keyboard = [
        [InlineKeyboardButton("⚖️ Maintain current weight", callback_data="goal_keep_as_it_is")],
        [InlineKeyboardButton("📉 Lose weight", callback_data="goal_lost_weight")],
        [InlineKeyboardButton("📈 Gain weight/muscle", callback_data="goal_take_weight")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=goal_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def goal_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles goal selection and completes profile."""
    query = update.callback_query
    await query.answer("🎯 Goal set!")
    
    goal_mapping = {
        "goal_keep_as_it_is": "keep as it is",
        "goal_lost_weight": "lost weight",
        "goal_take_weight": "take weight"
    }
    
    goal = goal_mapping[query.data]
    context.user_data['profile_data']['goal'] = goal
    context.user_data['state'] = None
    
    completion_text = (
        f"🎉 **Profile Complete!** 🎉\n\n"
        f"Here's your summary:\n"
        f"👤 {context.user_data['profile_data']['sex'].capitalize()}, {context.user_data['profile_data']['age']} years\n"
        f"⚖️ {int(context.user_data['profile_data']['weight'])} kg, 📏 {int(context.user_data['profile_data']['height'])} cm\n"
        f"💪 {context.user_data['profile_data']['activity'].capitalize()} activity\n"
        f"🎯 Goal: {goal.capitalize()}\n\n"
        f"Ready to calculate your daily calorie needs? 🔥"
    )
    
    keyboard = [[InlineKeyboardButton("🔥 Calculate My Calories", callback_data="calculate_calories")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=completion_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def use_existing_data_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles using existing profile data."""
    query = update.callback_query
    await query.answer("✅ Using your profile!")

    user_data = get_latest_user_data(update.effective_chat.id)
    if not user_data:
        await query.edit_message_text(
            text="❌ Sorry, I couldn't find your data. Let's create a new profile!"
        )
        await start_new_profile(update, context)
        return

    # Copy existing data to profile_data
    context.user_data['profile_data'] = {
        'sex': user_data['sex'],
        'weight': user_data['weight'],
        'height': user_data['height'],
        'age': user_data['age'],
        'activity': user_data['activity'],
        'goal': user_data['goal']
    }

    confirmation_text = (
        f"✅ **Using Your Current Profile** ✅\n\n"
        f"👤 {user_data['sex'].capitalize()}, {int(user_data['age'])} years\n"
        f"⚖️ {int(user_data['weight'])} kg, 📏 {int(user_data['height'])} cm\n"
        f"💪 {user_data['activity'].capitalize()} activity\n"
        f"🎯 Goal: {user_data['goal'].capitalize()}\n\n"
        f"Would you like to recalculate your calories or generate a menu? 🤔"
    )

    keyboard = [
        [InlineKeyboardButton("🔥 Recalculate Calories", callback_data="calculate_calories")],
        [InlineKeyboardButton("🗓️ Generate Menu", callback_data="generate_menu_confirmed")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text=confirmation_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def calculate_calories_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Calculates and displays daily calorie needs."""
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        text="🔥 Calculating your personalized calorie needs...\n\nThis will just take a moment! ⏳"
    )

    # Get data from either new profile or existing data
    profile_data = context.user_data.get('profile_data', {})
    if not profile_data:
        user_data = get_latest_user_data(update.effective_chat.id)
        if user_data:
            profile_data = {
                'sex': user_data['sex'],
                'weight': user_data['weight'],
                'height': user_data['height'],
                'age': user_data['age'],
                'activity': user_data['activity'],
                'goal': user_data['goal']
            }

    if not profile_data:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ Error: Could not find your profile data. Please create your profile first!"
        )
        await send_main_menu(update, context)
        return

    # Calculate BMR using Mifflin-St Jeor equation
    sex = profile_data['sex']
    weight = profile_data['weight']
    height = profile_data['height']
    age = profile_data['age']
    activity = profile_data['activity']

    if sex == 'man':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:  # woman
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    # Apply activity multiplier
    activity_multiplier = ACTIVITY_MULTIPLIERS.get(activity, 1.2)
    daily_calories = bmr * activity_multiplier

    # Save complete profile data to CSV
    complete_profile = profile_data.copy()
    complete_profile['chat_id'] = update.effective_chat.id
    complete_profile['calories'] = int(round(daily_calories))
    store_user_data(complete_profile)

    await asyncio.sleep(1.5)  # Small delay for realism

    result_text = (
        f"🎉 **Your Daily Calorie Target** 🎉\n\n"
        f"🔥 **{int(round(daily_calories))} calories per day**\n\n"
        f"📊 **Breakdown:**\n"
        f"• Base metabolic rate: {int(bmr)} cal\n"
        f"• Activity multiplier: {activity_multiplier}x\n"
        f"• Goal: {profile_data['goal'].capitalize()}\n\n"
        f"💡 This is your maintenance level. I'll adjust portions in your meal plan based on your goal!\n\n"
        f"What's next? 🤔"
    )

    keyboard = [
        [InlineKeyboardButton("🗓️ Generate My Meal Plan", callback_data="generate_menu_confirmed")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=result_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )

async def generate_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Generates a weekly meal plan using AI."""
    query = update.callback_query
    await query.answer()

    if not client:
        await query.edit_message_text(
            text="❌ Sorry, the AI service is currently unavailable.\n\n"
                 "Please try again later! 😔"
        )
        return

    # Get the latest user data
    user_data = get_latest_user_data(update.effective_chat.id)
    if not user_data:
        await query.edit_message_text(
            text="❌ I couldn't find your profile data.\n\n"
                 "Please create your profile first!"
        )
        await send_main_menu(update, context)
        return

    # Show generating message
    await query.edit_message_text(
        text="🤖 **Creating Your Personalized Menu** 🤖\n\n"
             "🔄 Analyzing your profile...\n"
             "🥗 Designing balanced meals...\n"
             "📊 Calculating portions...\n\n"
             "This may take 30-60 seconds. Please wait! ⏳"
    )

    # Send typing action
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    system_prompt = (
        "You are a professional nutritionist creating personalized 7-day meal plans. "
        "Create a JSON response with a 'menu' key containing an array of 7 day objects. "
        "Each day object must have: day, calories, macronutrients, breakfast, snack1, lunch, snack2, dinner. "
        "Make meals practical, detailed with portions and calories, balanced and realistic for home cooking. "
        "Adjust calories based on goals: deficit for weight loss, surplus for weight gain. "
        "RESPOND ONLY WITH VALID JSON - NO OTHER TEXT."
    )

    user_message = (
        f"Create a meal plan for:\n"
        f"Gender: {user_data['sex']}\n"
        f"Age: {int(user_data['age'])}\n"
        f"Height: {int(user_data['height'])} cm\n"
        f"Weight: {int(user_data['weight'])} kg\n"
        f"Activity: {user_data['activity']}\n"
        f"Goal: {user_data['goal']}\n"
        f"Target calories: {user_data.get('calories', 2000)}"
    )

    try:
        response = await asyncio.to_thread(
            client.complete,
            messages=[
                SystemMessage(system_prompt),
                UserMessage(user_message)
            ],
            model="openai/gpt-4.1-nano",
            temperature=0.7,
        )

        ai_response_content = response.choices[0].message.content
        menu_data = json.loads(ai_response_content)

        # Store menu for pagination
        context.user_data['menu_data'] = menu_data.get('menu', [])
        context.user_data['current_menu_day'] = 0

        if not context.user_data['menu_data']:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Sorry, I couldn't generate your menu right now.\n\n"
                     "Please try again in a moment! 🔄"
            )
            await send_main_menu(update, context)
            return

        # Success message before showing menu
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="🎉 **Your Personalized Menu is Ready!** 🎉\n\n"
                 "I've created a balanced 7-day meal plan just for you!\n"
                 "Use the navigation buttons to explore each day. 📅"
        )

        await display_menu_page(update, context, 0)

    except (Exception, json.JSONDecodeError) as e:
        print(f"Menu generation error: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ **Oops! Something went wrong** 😔\n\n"
                 "I couldn't generate your menu right now. This might be due to:\n"
                 "• High server load\n"
                 "• Temporary AI service issues\n\n"
                 "💡 **Try again in a few minutes!**"
        )
        await send_main_menu(update, context, "Let's try again later! 🔄")

async def display_menu_page(update: Update, context: ContextTypes.DEFAULT_TYPE, day_index: int):
    """Displays a single day of the menu with navigation."""
    menu_data = context.user_data.get('menu_data')
    if not menu_data or day_index < 0 or day_index >= len(menu_data):
        await send_main_menu(update, context, "Menu data not found. Let's start over! 🔄")
        return

    day_menu = menu_data[day_index]
    
    # Format the daily menu
    day_text = f"📅 **{day_menu.get('day', f'Day {day_index + 1}')}**"
    calories_text = f"🔥 **{day_menu.get('calories', 'N/A')} calories**"
    macros_text = f"📊 **{day_menu.get('macronutrients', 'N/A')}**"
    
    meals_text = ""
    meal_emojis = {"breakfast": "🥞", "snack1": "🍎", "lunch": "🍽️", "snack2": "🥨", "dinner": "🍖"}
    
    for meal_key, emoji in meal_emojis.items():
        meal_content = day_menu.get(meal_key, "")
        if meal_content:
            meal_name = meal_key.replace("snack1", "Morning Snack").replace("snack2", "Afternoon Snack").capitalize()
            meals_text += f"\n{emoji} **{meal_name}:**\n{meal_content}\n"
    
    message_text = f"{day_text}\n{calories_text}\n{macros_text}\n{meals_text}"
    
    # Navigation buttons
    keyboard = []
    nav_row = []
    
    if day_index > 0:
        nav_row.append(InlineKeyboardButton("◀️ Previous Day", callback_data="menu_prev"))
    if day_index < len(menu_data) - 1:
        nav_row.append(InlineKeyboardButton("Next Day ▶️", callback_data="menu_next"))
    
    if nav_row:
        keyboard.append(nav_row)
    
    # Progress indicator
    progress_text = f"📍 Day {day_index + 1} of {len(menu_data)}"
    keyboard.append([InlineKeyboardButton(progress_text, callback_data="noop")])
    keyboard.append([InlineKeyboardButton("🏠 Back to Main Menu", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.edit_message_text(
            chat_id=update.effective_chat.id,
            message_id=update.effective_message.message_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    except Exception:
        # If edit fails, send new message
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )

async def menu_navigation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles menu navigation (next/previous day)."""
    query = update.callback_query
    await query.answer()

    current_day = context.user_data.get('current_menu_day', 0)
    
    if query.data == "menu_next":
        current_day += 1
    elif query.data == "menu_prev":
        current_day -= 1
    elif query.data == "noop":
        return  # Do nothing for progress indicator
    
    context.user_data['current_menu_day'] = current_day
    await display_menu_page(update, context, current_day)

async def back_to_main_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Returns to main menu."""
    query = update.callback_query
    await query.answer("🏠 Going to main menu")
    
    context.user_data['state'] = None  # Clear any ongoing states
    await send_main_menu(update, context, "Welcome back! What would you like to do? 🌟")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles errors gracefully."""
    print(f"Update '{update}' caused error '{context.error}'")

    try:
        if isinstance(context.error, NetworkError):
            error_message = (
                "🌐 **Connection Issue** 🌐\n\n"
                "There seems to be a temporary network problem.\n"
                "Please try again in a moment! 🔄"
            )
        else:
            error_message = (
                "❌ **Oops! Something went wrong** ❌\n\n"
                "Don't worry, I'm still here to help!\n"
                "Try using /start to begin fresh. 😊"
            )

        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=error_message,
            parse_mode='Markdown'
        )
    except Exception as e:
        print(f"Error in error handler: {e}")

def main():
    """Main function to run the bot."""
    if not BOT_TOKEN:
        print("❌ Error: TELEGRAM_BOT_TOKEN not found in environment variables.")
        print("Please add TELEGRAM_BOT_TOKEN to your .env file.")
        return
    
    initialize_csv()
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Command handlers
    application.add_handler(CommandHandler('start', start_command))
    
    # Main menu callbacks
    application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^(fill_in|generate_menu)$'))
    
    # Profile flow callbacks
    application.add_handler(CallbackQueryHandler(sex_choice_callback, pattern='^sex_(male|female)$'))
    application.add_handler(CallbackQueryHandler(activity_choice_callback, pattern='^activity_'))
    application.add_handler(CallbackQueryHandler(goal_choice_callback, pattern='^goal_'))
    application.add_handler(CallbackQueryHandler(use_existing_data_callback, pattern='^use_existing_data$'))
    application.add_handler(CallbackQueryHandler(start_new_profile, pattern='^start_new_profile$'))
    
    # Calculation and menu generation
    application.add_handler(CallbackQueryHandler(calculate_calories_callback, pattern='^calculate_calories$'))
    application.add_handler(CallbackQueryHandler(generate_menu_callback, pattern='^generate_menu_confirmed$'))
    
    # Menu navigation
    application.add_handler(CallbackQueryHandler(menu_navigation_callback, pattern='^menu_(next|prev|noop)$'))
    
    # Navigation callbacks
    application.add_handler(CallbackQueryHandler(back_to_main_callback, pattern='^back_to_main$'))
    
    # Text input handler
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_text_input))

    # Error handler
    application.add_error_handler(error_handler)
    
    # Run the bot
    print("Bot is running... 🤖")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()