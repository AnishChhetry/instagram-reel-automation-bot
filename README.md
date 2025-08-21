# 🎬 Instagram Reel Pro Automation Bot

A comprehensive tool built with Streamlit and Python to automate the scheduling and posting of Instagram Reels. This application provides a user-friendly interface to manage single-use posts and set up recurring daily posts.

---

## ✨ Key Features

-   **Dashboard Analytics**: View key metrics like total posts, follower count, engagement rate, and reach directly from the dashboard.
-   **Single Post Scheduling**: Upload a video, write a caption, and schedule it to be posted at a specific date and time in your local timezone (IST).
-   **Recurring Daily Posts**: Set up a schedule to post one video automatically at three different times every day.
-   **Post Management**: View, edit the schedule of, and delete upcoming posts.
-   **Secure Configuration**: All API keys and sensitive credentials are managed securely through an environment file.
-   **Robust Scheduling**: Uses `APScheduler` with a persistent database to manage and track scheduled jobs, even after an application restart.

---

## 📂 Project Structure

The project is organized into several modules, each with a specific responsibility:

-   `src/app.py`: The main Streamlit application file that renders the user interface and handles user interactions.
-   `src/instagram_api.py`: A class that manages all interactions with the Instagram Graph API, including posting reels and fetching analytics.
-   `src/scheduler.py`: The core scheduling engine powered by `APScheduler`. It manages both single-use and recurring jobs.
-   `src/video_processor.py`: A utility class for handling video file uploads, validation, and storage.
-   `src/config.py`: Manages loading and saving of application settings and API credentials from the `.env` file.
-   `data/`: Directory for storing persistent data like the scheduler database, logs, and uploaded videos.
-   `config/.env`: The environment file where you store your secret keys and API credentials.

---

## 🚀 Setup and Installation

Follow these steps to get the application running on your local machine.

### **1. Prerequisites**

-   Python 3.10 or higher
-   A [Meta for Developers](https://developers.facebook.com/) account and an app with the necessary permissions (`instagram_content_publish`).
-   An [ngrok](https://ngrok.com/) account and authtoken for exposing your local server to the internet.

### **2. Clone the Repository**

```bash
git clone https://github.com/AnishChhetry/instagram-reel-automation-bot.git
cd instagram-reel-automation-bot
```

### **3. Set Up a Virtual Environment**

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
# Create the virtual environment
python -m venv env

# Activate it
# On macOS/Linux:
source env/bin/activate
# On Windows:
.\env\Scripts\activate
```

### **4. Install Dependencies**

Create a `requirements.txt` file in the root directory with the following content:

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
```

Then, run the installation command:

```bash
pip install -r requirements.txt
```

### **5. Configure Your Credentials**

-   Navigate to the `config/` directory.
-   Create a file named `.env`.
-   Open the `.env` file and fill in your credentials.

```ini
# Meta/Instagram API Credentials
ACCESS_TOKEN="YOUR_LONG_LIVED_INSTAGRAM_ACCESS_TOKEN"
APP_ID="YOUR_META_APP_ID"
APP_SECRET="YOUR_META_APP_SECRET"
INSTAGRAM_ACCOUNT_ID="YOUR_INSTAGRAM_ACCOUNT_ID"

# Ngrok Authtoken
NGROK_AUTHTOKEN="YOUR_NGROK_AUTHTOKEN"
```

### **6. Run the Application**

Navigate back to the `src/` directory and launch the Streamlit app.

```bash
cd src
streamlit run app.py
```

Your application should now be running and accessible in your web browser!

---

## ⚙️ Usage

Once the application is running, you can use the different tabs to manage your content.

-   **Settings**: The first time you run the app, go to this tab to enter and save your API credentials.
-   **Upload & Schedule**: For posting a video once. You can choose to "Post Now" or "Schedule for Later" at a specific date and time (in IST).
-   **Recurring Post**: To set up a daily schedule. Upload a video, write a caption, and choose three times of the day for it to be posted automatically.
-   **Scheduled Posts**: View all your upcoming single-use posts. You can edit their scheduled time or delete them from here.
-   **Analytics Dashboard**: Get a quick overview of your account's performance.

---

## ⚠️ Important Notes

-   **Local Server Requirement**: For the scheduler to work, your computer must be on and the Streamlit application must be running. If you close the application, the scheduler will stop.
-   **Instagram Content Policy**: Be mindful of Instagram's policies. Posting the exact same content repeatedly may be flagged by their algorithm. Consider varying captions for recurring posts.
