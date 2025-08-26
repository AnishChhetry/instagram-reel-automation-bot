# 🎬 ReelPilot AI: Instagram Automation & Analysis

A comprehensive tool built with Streamlit and Python to automate the scheduling of Instagram Reels and provide powerful, AI-driven account analysis.

---

## ✨ Key Features

-   **Multi-Functional Hub**: A central landing page to navigate between post management and account analysis.
-   **Secure Access**: Optional PIN protection to secure the post management dashboard.
-   **🤖 AI-Powered Account Analysis**:
    -   Leverages Google's Gemini AI to generate in-depth, real-time analysis for any public Instagram Business or Creator account.
    -   Provides actionable insights on engagement, content strategy, and posting cadence.
-   **Advanced Post Scheduling**:
    -   Upload a video, write a caption, and schedule it for a specific date and time.
    -   Set up recurring daily posts with multiple time slots.
-   **Comprehensive Dashboard**:
    -   View key metrics like follower count, engagement rate, and reach.
    -   Analyze the performance of individual videos.
-   **Full Post Management**: View, edit the schedule of, and delete upcoming posts.
-   **Secure & Robust**:
    -   Manages all credentials securely through an environment file.
    -   Uses `APScheduler` with a persistent database to ensure scheduled jobs are not lost on application restart.

---

## 📂 Project Structure

-   `src/app.py`: The main Streamlit application file that renders the UI and handles user interactions.
-   `src/instagram_api.py`: A class that manages all interactions with the Instagram Graph API and Google's Generative AI.
-   `src/scheduler.py`: The core scheduling engine powered by `APScheduler`.
-   `src/video_processor.py`: A utility for handling video file uploads, validation, and storage.
-   `src/config.py`: Manages loading and saving of application settings and API credentials from the `.env` file.
-   `data/`: Directory for storing persistent data (scheduler DB, logs, videos).
-   `config/.env`: The environment file for your secret keys and credentials.

---

## 🚀 Setup and Installation

### **1. Prerequisites**

-   Python 3.10 or higher
-   A [Meta for Developers](https://developers.facebook.com/) account and an app with `instagram_content_publish` permissions.
-   An [ngrok](https://ngrok.com/) account and authtoken.
-   A [Google AI Studio](https://aistudio.google.com/) API key for the analysis feature.

### **2. Clone the Repository**

```bash
git clone [https://github.com/AnishChhetry/instagram-reel-automation-bot.git](https://github.com/AnishChhetry/instagram-reel-automation-bot.git)
cd instagram-reel-automation-bot
```

### **3. Set Up a Virtual Environment**

```bash
# Create and activate the virtual environment
python -m venv env
source env/bin/activate  # On macOS/Linux
# .\env\Scripts\activate  # On Windows
```

### **4. Install Dependencies**

Create a `requirements.txt` file with the following content:

```text
streamlit
pandas
plotly-express
numpy
python-dotenv
apscheduler
SQLAlchemy
requests
pyngrok
pytz
google-generativeai
```

Then, install the packages:

```bash
pip install -r requirements.txt
```

### **5. Configure Your Credentials**

-   Navigate to the `config/` directory and create a file named `.env`.
-   Fill in your credentials as shown below.

```ini
# Meta/Instagram API Credentials
ACCESS_TOKEN="YOUR_LONG_LIVED_INSTAGRAM_ACCESS_TOKEN"
APP_ID="YOUR_META_APP_ID"
APP_SECRET="YOUR_META_APP_SECRET"
INSTAGRAM_ACCOUNT_ID="YOUR_INSTAGRAM_ACCOUNT_ID"

# Ngrok Authtoken
NGROK_AUTHTOKEN="YOUR_NGROK_AUTHTOKEN"

# Google AI API Key (for analysis feature)
GOOGLE_API_KEY="YOUR_GOOGLE_AI_API_KEY"

# Application Security (Optional)
# Set a PIN to lock the post management dashboard
APP_PIN="YOUR_SECRET_PIN"
```

### **6. Run the Application**

Navigate to the `src/` directory and launch the Streamlit app:

```bash
cd src
streamlit run app.py
```

---

## ⚙️ Usage

1.  **Configuration**: On the landing page, expand the "Application Configuration & Settings" section. Enter all your API keys and optionally set an access PIN. Click "Save Configuration".
2.  **Choose an Action**:
    -   Click **"Analyze an Account"** to access the AI analysis tool. Enter any public Instagram Business/Creator username to get a detailed report.
    -   Click **"Manage My Posts"** to go to the scheduling dashboard. If you set a PIN, you will be prompted to enter it.
3.  **Inside the Dashboard**:
    -   **Upload & Schedule**: For posting a single video.
    -   **Recurring Post**: To set up a daily posting schedule.
    -   **Performance**: Analyze your recent videos' engagement metrics.
    -   **Scheduled Posts**: View, edit, or delete your upcoming posts.

---

## ⚠️ Important Notes

-   **Local Server Requirement**: For the scheduler to post content, your computer must be on and the Streamlit application must be running.
-   **Content Policy**: Be mindful of Instagram's policies. Repeatedly posting identical content may be flagged. Consider using the caption editor to vary your text.
