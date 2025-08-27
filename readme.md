# 🤖 Telegram Concise AI Assistant

This is a straightforward Telegram bot that provides brief, direct answers to user messages by leveraging AI API.

---

## ✨ Features

- **Concise AI Responses:** Fetches short, one-to-two sentence answers from an AI model.
- **Secure Configuration:** Securely loads sensitive API tokens from a `.env` file.

---

## 🚀 Getting Started

Follow these steps to set up and run the bot locally.

### Prerequisites

You will need the following API tokens:
1.  **A Telegram Bot Token:** Obtain this by talking to [@BotFather](https://telegram.me/BotFather) on Telegram.
2.  **A GitHub Token:** This token requires access to the GitHub AI Inference API endpoint.

### Installation

1.  **Clone the repository:**
    ```
    git clone https://github.com/saprykins/telegram_test_bot
    cd telegram_test_bot
    ```

2.  **Create and activate a virtual environment:**
    -   **On macOS/Linux:**
        ```
        virtualenv venv
        source venv/bin/activate
        ```
    -   **On Windows:**
        ```
        py -m venv venv
        venv\Scripts\activate
        ```

3.  **Install dependencies:**
    ```
    pip install -r requirements.txt
    ```

### Configuration

1.  In the root directory of the project, create a file named `.env`.
2.  Add your API tokens to this file as shown below, replacing the placeholder values.

    ```
    TELEGRAM_BOT_TOKEN="YOUR_TELEGRAM_BOT_TOKEN"
    GITHUB_TOKEN="YOUR_GITHUB_TOKEN"
    ```

### Running the Bot

Execute the following command from your terminal:

```
python my_bot.py
```

<!--
## ✨ Future improvements  
Enrich default settings  
Use the bot in groups  
Bot inserts data into google sheets or database  
Voice to text  



# Sources
# Official doc from telegram:  
https://core.telegram.org/bots
https://core.telegram.org/bots/api
https://github.com/python-telegram-bot/python-telegram-bot


Free deployment  
Norht Europe
free tier - Standard B1s (1 vcpu, 1 GiB memory)
free tier - Storage
Initially, it was created with public IP, i connected to user qwerty_05112024, uploaded the code
NB: what you see in ssh isn't correlated with cloudshell vscode

There're costs related to public IP
i deleted it when VM stoped from network interfaces
i should connect via developer bastion (should be free - to be checked)
i could access only to user azureuser
NB: copy past was complicated
i used: 
wget https://raw.githubusercontent.com/saprykins/telegram_test_bot/main/my_bot.py
copy paste + new lines for credentials
-->




## 📈 Azure VM Capacity Tests

This report summarizes performance tests on an **Azure Standard B1s Virtual Machine** to evaluate its capacity for a bot application. The goal was to understand its limits as a cost-effective, free-tier option.

---

### **Test Scenario**

The bot was tested with two simulated users:

* **Stress Test User:** Continuously flooded the bot with requests to identify its breaking point under sustained load.
* **Normal User:** Sent requests from a separate chat line to simulate typical usage.

### **Performance**

The VM successfully managed both workloads. Brief spikes in **CPU usage** and **network traffic** occurred during the stress test, yet the VM remained stable and continued to serve the normal user without issue. This demonstrates the **Standard B1s** can effectively handle sudden, heavy workloads.

### **Conclusion**

The **Standard B1s** is suitable for a bot with a small user base and is a reliable, cost-effective choice for similar applications with intermittent, bursty activity.

---

The charts below illustrate the VM's behavior during the two-user stress test.

![VM capacity tests](images/perf_tests.png "VM capacity tests 2")  