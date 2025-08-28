# Personal Nutrition Bot 🍎

This Telegram bot serves as your personal nutrition assistant. It calculates your daily calorie needs and generates a custom 7-day meal plan based on your body data and fitness goals.

## ✨ Features

-   **Personalized Data Input:** Easily enter your sex, age, weight, height, and activity level via the bot's interactive prompts.
-   **Calorie Calculation:** Get an accurate estimate of your daily calorie needs using the Mifflin-St Jeor formula.
-   **Goal-Based Planning:** Set your goal—whether it's to lose, maintain, or gain weight—and the bot will adjust your meal plan accordingly.
-   **AI-Powered Meal Plans:** Uses a powerful AI model to generate a custom 7-day menu with detailed meals, including calories and macronutrient breakdowns.
-   **User-Friendly Interface:** Navigate the bot with simple buttons and clear prompts.

## 🚀 Getting Started

Follow these steps to set up and run the bot locally.

### Prerequisites

-   Python 3.8 or higher
-   A Telegram Bot Token (from [BotFather](https://t.me/botfather))
-   A GitHub AI Token or Azure AI Inference Key

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/your-repo-name.git
    cd your-repo-name
    ```

2.  **Create and activate a virtual environment:**

    -   **On macOS/Linux:**
        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```
    -   **On Windows:**
        ```bash
        python -m venv venv
        venv\Scripts\activate
        ```

3.  **Install the required Python packages:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Create a `.env` file:**
    Create a file named `.env` in the project root directory and add your API tokens:

    ```dotenv
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    GITHUB_TOKEN="YOUR_GITHUB_TOKEN"
    ```
    > **Note:** The code is configured to use a GitHub AI token as a credential for the AI service.

5.  **Run the bot:**

    ```bash
    python main.py
    ```

### Usage

1.  Open Telegram and find your bot by its username.
2.  Send the `/start` command to initiate the conversation.
3.  Follow the prompts to enter your personal data and generate your meal plan.

## 📸 Demo

Here's a quick look at how to input your information into the bot:

![Information Input Demo](images/information_input.GIF)



<video width="320" height="240" controls>
  <source src="/images/information_input.mp4" type="video/mp4">
  Your browser does not support the video tag.
</video>

https://user-images.githubusercontent.com/username/video.mp4



![Information Input Demo](images/output-15.gif)
