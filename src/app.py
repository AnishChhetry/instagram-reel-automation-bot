# -*- coding: utf-8 -*-
"""
Main Streamlit application for ReelPilot AI.

This script initializes and runs the user interface for managing, scheduling,
and analyzing an Instagram presence. It handles UI rendering, state management,
and user interactions, serving as the central hub for the application's features.

Key functionalities include:
- A multi-page interface (Landing, Analysis, Management).
- Secure PIN-based authentication for the management dashboard.
- Real-time Instagram account analysis using Google's Gemini AI.
- Single and recurring Reel scheduling.
- Performance analytics and account details display.
"""

import streamlit as st
import uuid
import pandas as pd
from datetime import datetime, timedelta, time
from pathlib import Path
import plotly.express as px
import numpy as np
import pytz
import os

from instagram_api import InstagramAPI
from scheduler import ReelScheduler
from video_processor import VideoProcessor
from config import Config

# --- Page and Session Initialization ---

st.set_page_config(
    page_title="ReelPilot AI",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .stButton>button {
        height: 3em;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables to manage application state across reruns.
# This prevents re-initialization of components on every user interaction.
if 'config' not in st.session_state:
    st.session_state.config = Config()
if 'api' not in st.session_state:
    st.session_state.api = InstagramAPI(st.session_state.config)
if 'scheduler' not in st.session_state:
    st.session_state.scheduler = None
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'app_mode' not in st.session_state:
    st.session_state.app_mode = 'landing'

# --- Core Component Functions ---

def initialize_components():
    """
    Initializes core components like the ReelScheduler if the app is configured.

    This function checks if the necessary API credentials are present in the
    configuration. If so, it instantiates the scheduler, making it available.

    Returns:
        bool: True if the application is configured, False otherwise.
    """
    config = st.session_state.config
    is_configured = config.is_configured()

    if is_configured and st.session_state.scheduler is None:
        st.session_state.scheduler = ReelScheduler()
    return is_configured

def render_sidebar():
    """
    Renders the sidebar for the main management dashboard.

    The sidebar contains automation controls, quick actions like refreshing data,
    and a system status panel displaying API connectivity and usage metrics.
    """
    st.sidebar.markdown("### ⚙️ Automation Controls")
    is_configured = st.session_state.config.is_configured()

    # Automation toggle (enables/disables the scheduler)
    if is_configured and st.session_state.scheduler:
        scheduler_status = st.session_state.scheduler.get_scheduler_status()
        is_enabled = scheduler_status.get('running', False)
        scheduler_enabled = st.sidebar.toggle("Enable Automation", value=is_enabled, help="Turn automation on/off")
        if scheduler_enabled != is_enabled:
            if scheduler_enabled:
                st.session_state.scheduler.resume_scheduler()
            else:
                st.session_state.scheduler.pause_scheduler()
            st.rerun()
    else:
        st.sidebar.toggle("Enable Automation", value=False, disabled=True)

    # Quick actions and system status
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🚀 Quick Actions")
    if st.sidebar.button("🏠 Back to Home", use_container_width=True):
        st.session_state.app_mode = 'landing'
        st.rerun()
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()
    if st.sidebar.button("⚡ Test API Connection", use_container_width=True, disabled=not is_configured):
        test_api_connection()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 System Status")
    if is_configured and st.session_state.api:
        st.sidebar.metric("API Status", "✅ Connected")
        if st.session_state.scheduler:
            st.sidebar.metric("Scheduled Posts", st.session_state.scheduler.get_scheduler_status().get('total_posts', 0))
        limit_info = st.session_state.api.get_content_publishing_limit()
        if limit_info.get('success') and 'data' in limit_info and limit_info['data']:
            usage = limit_info['data']['data'][0].get('quota_usage', 'NA')
            st.sidebar.metric("Daily API Posts Used", usage)
    else:
        st.sidebar.metric("API Status", "❌ Disconnected")

def test_api_connection():
    """
    Tests the connection to the Instagram Graph API and displays the result.
    """
    with st.spinner("Testing API connection..."):
        result = st.session_state.api.test_connection()
        if result["success"]:
            st.sidebar.success("✅ API Connection Successful")
        else:
            st.sidebar.error(f"❌ API Error: {result.get('error', 'Unknown error')}")

# --- Main UI Rendering Functions ---

def render_main_dashboard():
    """
    Renders the main dashboard UI for post management and analytics.

    This function sets up the header, key performance indicator (KPI) metrics,
    and the tabbed interface for different management tasks, including settings.
    """
    # --- FIX: Moved success message logic here from the landing page ---
    if st.session_state.get("config_saved"):
        st.success("✅ Configuration saved successfully!")
        del st.session_state.config_saved

    st.markdown("""
    <div class="main-header">
        <h1>🎬 ReelPilot AI</h1>
        <p>Manage, schedule, and analyze your Instagram presence</p>
    </div>
    """, unsafe_allow_html=True)
    
    tabs = ["📤 Upload & Schedule", "🔁 Recurring Post", "🚀 Performance", "📅 Scheduled Posts", "👤 Account Details", "⚙️ Settings"]
    tab_upload, tab_recurring, tab_performance, tab_scheduled, tab_details, tab_settings = st.tabs(tabs)

    is_configured = initialize_components()

    # Fetch data for dashboard metrics
    with st.spinner("Loading dashboard data..."):
        account_info = st.session_state.api.test_connection() if is_configured else {}
        media_info = st.session_state.api.get_user_media(limit=25) if is_configured else {}
        insights_info = st.session_state.api.get_account_insights(period='days_28') if is_configured else {}

    # Calculate and display KPIs
    total_posts, followers, reach, engagement_rate = 'NA', 'NA', 'NA', 'NA'
    if account_info.get('success'):
        data = account_info['data']
        total_posts, followers = data.get('media_count', 'NA'), data.get('followers_count', 0)
    if insights_info.get('success') and 'data' in insights_info and insights_info['data'].get('data'):
        for metric in insights_info['data']['data']:
            if metric['name'] == 'reach' and metric['values']: reach = f"{metric['values'][0].get('value', 0):,}"
    if media_info.get('success') and 'data' in media_info and followers and isinstance(followers, int) and followers > 0:
        recent_posts = media_info['data']['data']
        total_likes = sum(p.get('like_count', 0) for p in recent_posts)
        total_comments = sum(p.get('comments_count', 0) for p in recent_posts)
        if recent_posts:
            avg_interactions = (total_likes + total_comments) / len(recent_posts)
            engagement_rate = f"{(avg_interactions / followers) * 100:.2f}%"

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 Total Posts", total_posts)
    col2.metric("👥 Followers", f"{followers:,}" if isinstance(followers, int) else followers)
    col3.metric("❤️ Engagement Rate", engagement_rate, help="Based on last 25 posts")
    col4.metric("👀 Reach (28 days)", reach)
    st.markdown("---")

    def show_config_warning():
        """Displays a standard warning message if the app is not configured."""
        st.warning("⚠️ Application not configured. Please go to the '⚙️ Settings' tab to enter your API credentials.")

    with tab_upload:
        if is_configured: render_upload_tab()
        else: show_config_warning()
        
    with tab_recurring:
        if is_configured: render_recurring_post_tab()
        else: show_config_warning()

    with tab_performance:
        if is_configured: render_performance_tab(media_info)
        else: show_config_warning()

    with tab_scheduled:
        if is_configured: render_scheduled_posts_tab()
        else: show_config_warning()

    with tab_details:
        if is_configured: render_account_details_tab()
        else: show_config_warning()
        
    with tab_settings:
        st.header("⚙️ Application Configuration")
        st.info("Enter your API credentials and application settings here. Changes are applied immediately after saving.")
        render_settings_form(form_key="dashboard_settings_form")

def render_settings_form(form_key="settings_form"):
    """
    Renders the configuration form for setting up API keys and app settings.

    Args:
        form_key (str): A unique key for the Streamlit form to prevent conflicts.
    """
    with st.form(form_key):
        config = st.session_state.config

        st.subheader("🔑 Application Access")
        app_pin = st.text_input("Application Access PIN (leave blank to disable)", value=config.app_pin or "", type="password", help="Set a PIN to lock access to the post management dashboard.")

        st.subheader("🤖 Google AI for Analysis")
        google_api_key = st.text_input("Google AI API Key", value=config.google_api_key or "", type="password", help="Required for the AI Account Analysis feature.")

        st.subheader("🔧 Instagram API Credentials")
        access_token = st.text_input("Access Token", value=config.access_token or "", type="password")
        app_id = st.text_input("App ID", value=config.app_id or "")
        app_secret = st.text_input("App Secret", value=config.app_secret or "", type="password")
        instagram_id = st.text_input("Instagram Account ID", value=config.instagram_account_id or "")

        st.subheader("🔗 Ngrok Configuration")
        ngrok_token = st.text_input("Ngrok Authtoken", value=config.ngrok_authtoken or "", type="password")

        if st.form_submit_button("💾 Save Configuration", type="primary", use_container_width=True):
            config_data = {
                "ACCESS_TOKEN": access_token, "APP_ID": app_id, "APP_SECRET": app_secret,
                "INSTAGRAM_ACCOUNT_ID": instagram_id, "NGROK_AUTHTOKEN": ngrok_token,
                "APP_PIN": app_pin, "GOOGLE_API_KEY": google_api_key
            }
            if config.save_config(config_data):
                st.session_state.config_saved = True
                # Forcefully re-initialize core components to apply new settings immediately.
                st.session_state.config = Config()
                st.session_state.api = InstagramAPI(st.session_state.config)
                # Clear dependent components to ensure they are recreated with the new config.
                if 'scheduler' in st.session_state: del st.session_state.scheduler
                if 'authenticated' in st.session_state: del st.session_state.authenticated
                st.rerun()
            else:
                st.error("❌ Failed to save configuration file.")

# --- Tab-Specific Rendering Functions ---

def render_account_details_tab():
    """Renders the 'Account Details' tab, showing raw account data."""
    st.header("👤 Instagram Account Details")
    with st.spinner("Fetching account details..."):
        account_info = st.session_state.api.test_connection()
    if account_info.get('success'):
        st.subheader("Account Overview")
        st.json(account_info['data'])
    else:
        st.error(f"Could not fetch account details: {account_info.get('error')}")

def render_upload_tab():
    """Renders the 'Upload & Schedule' tab for single-use posts."""
    st.header("📤 Upload & Schedule a Reel")
    uploaded_file = st.file_uploader("Choose a video file", type=st.session_state.config.allowed_video_formats)
    if uploaded_file:
        st.radio("When to post?", ["📤 Post Now", "⏰ Schedule for Later"], horizontal=True, key="schedule_type")
        with st.form("reel_form"):
            caption = st.text_area("Caption", height=100, max_chars=2200)
            if st.session_state.schedule_type == "⏰ Schedule for Later":
                now_in_ist = datetime.now(pytz.timezone('Asia/Kolkata'))
                st.date_input("Date", min_value=now_in_ist.date(), key="schedule_date")
                st.time_input("Time (IST)", step=timedelta(minutes=1), key="schedule_time")

            submitted = st.form_submit_button("🚀 Process Reel", type="primary", use_container_width=True)
            if submitted:
                schedule_datetime = None
                if st.session_state.schedule_type == "⏰ Schedule for Later":
                    ist = pytz.timezone('Asia/Kolkata')
                    naive_datetime = datetime.combine(st.session_state.schedule_date, st.session_state.schedule_time)
                    schedule_datetime = ist.localize(naive_datetime)
                    if schedule_datetime < datetime.now(ist) + timedelta(minutes=1):
                        st.error("❌ Scheduled time must be at least one minute in the future.")
                        return
                process_reel_upload(uploaded_file, caption, st.session_state.schedule_type, schedule_datetime)

def process_reel_upload(uploaded_file, caption, schedule_type, schedule_datetime=None):
    """
    Handles the processing and posting/scheduling of an uploaded reel.

    Args:
        uploaded_file: The video file uploaded via Streamlit.
        caption (str): The caption for the reel.
        schedule_type (str): Either "📤 Post Now" or "⏰ Schedule for Later".
        schedule_datetime (datetime, optional): The scheduled time if applicable.
    """
    video_data = None
    try:
        vp = VideoProcessor(st.session_state.config)
        if schedule_type == "📤 Post Now":
            with st.spinner("Processing video..."):
                video_data = vp.process_uploaded_video(uploaded_file, is_temporary=True)
            with st.spinner("Posting reel to Instagram..."):
                result = st.session_state.api.post_reel(video_data['path'], caption)
            if result.get('success'):
                st.success(f"✅ Reel posted! Media ID: {result.get('media_id')}")
            else:
                st.error(f"❌ Failed to post reel: {result.get('error')}")
        else: # Schedule for later
            with st.spinner("Processing and saving video for schedule..."):
                video_data = vp.process_uploaded_video(uploaded_file, is_temporary=False)
            post_data = {
                "id": str(uuid.uuid4()), "video_path": video_data['path'],
                "caption": caption, "scheduled_time": schedule_datetime.isoformat()
            }
            st.session_state.scheduler.schedule_post(post_data)
            st.success(f"✅ Reel scheduled for {schedule_datetime.strftime('%Y-%m-%d at %H:%M %Z')}!")
    except Exception as e:
        st.error(f"❌ An error occurred: {e}")
    finally:
        # Clean up temporary video file after posting immediately.
        if video_data and schedule_type == "📤 Post Now":
            try:
                os.remove(video_data['path'])
                st.toast("Temporary file deleted.", icon="🗑️")
            except OSError as e:
                st.warning(f"Could not delete temporary file: {e}")

def render_recurring_post_tab():
    """Renders the 'Recurring Post' tab for setting up daily schedules."""
    st.header("🔁 Recurring Daily Post")
    schedule = st.session_state.scheduler.get_recurring_schedule()
    
    if schedule:
        st.subheader("Current Recurring Schedule")
        with st.container(border=True):
            st.write(f"**Video File:** `{schedule['video_path']}`")
            st.write("**Caption:**"); st.text(schedule['caption'])
            times_str = [time.fromisoformat(t).strftime('%I:%M %p') for t in schedule['times']]
            st.write(f"**Scheduled Times (IST):** {', '.join(times_str)}")
            if st.button("❌ Cancel Recurring Schedule", use_container_width=True, type="primary"):
                with st.spinner("Cancelling schedule..."):
                    st.session_state.scheduler.cancel_recurring_posts()
                st.success("Recurring schedule cancelled."); st.rerun()
    else:
        st.subheader("Set Up a New Recurring Schedule")
        st.info("Set one video to be posted automatically at your chosen times every day.")
        
        # Manage state for dynamic time inputs
        if 'num_recurring_times' not in st.session_state: st.session_state.num_recurring_times = 1
        if 'prev_num_recurring_times' not in st.session_state: st.session_state.prev_num_recurring_times = 1

        st.number_input("How many times per day?", min_value=1, max_value=10, key='num_recurring_times', step=1)
        
        # Rerun to update the number of time input fields if changed
        if st.session_state.num_recurring_times != st.session_state.prev_num_recurring_times:
            for i in range(st.session_state.prev_num_recurring_times):
                if f"recurring_time_{i}" in st.session_state: del st.session_state[f"recurring_time_{i}"]
            st.session_state.prev_num_recurring_times = st.session_state.num_recurring_times
            st.rerun()

        with st.form("recurring_form"):
            video_file = st.file_uploader("Choose a video for recurring posts", type=st.session_state.config.allowed_video_formats)
            caption = st.text_area("Recurring Caption", height=100)
            st.write("**Select the times of the day (IST):**")
            
            num_times = st.session_state.num_recurring_times
            selected_times = []
            interval = 24 // num_times
            start_hour = 9 # Sensible default starting time
            
            for i in range(num_times):
                default_hour = (start_hour + i * interval) % 24
                time_val = st.time_input(f"Time {i + 1}", value=time(default_hour, 0), key=f"recurring_time_{i}", step=timedelta(minutes=1))
                selected_times.append(time_val)

            submitted = st.form_submit_button("🚀 Start Recurring Schedule", use_container_width=True)
            if submitted:
                if not video_file: st.error("You must upload a video file.")
                else:
                    with st.spinner("Processing video and setting schedule..."):
                        try:
                            vp = VideoProcessor(st.session_state.config)
                            video_data = vp.process_uploaded_video(video_file)
                            st.session_state.scheduler.schedule_recurring_post(
                                video_path=video_data['path'], caption=caption, times=selected_times
                            )
                            st.success("Recurring schedule set successfully!"); st.rerun()
                        except Exception as e:
                            st.error(f"An error occurred: {e}")

def render_performance_tab(media_info):
    """
    Renders the 'Performance' tab with insights on recent videos.

    Args:
        media_info (dict): A dictionary containing data on recent media posts.
    """
    st.header("🚀 Video Performance Insights")
    st.write("Select one of your recent videos to view its detailed performance metrics.")
    if not media_info.get("success"):
        st.error("Could not fetch your recent media to analyze. Please check your API connection.")
        return
    
    media_list = media_info.get("data", {}).get("data", [])
    video_options = [m for m in media_list if m.get("media_type") in ["VIDEO", "REELS"]]
    if not video_options:
        st.warning("You don't have any recent videos/reels to analyze."); return

    def format_video_option(media_item: dict) -> str:
        """Formats a media item for display in a selectbox."""
        caption = media_item.get('caption', 'No caption')
        
        timestamp_str = media_item['timestamp']
        
        if timestamp_str[-5] in ('+', '-') and timestamp_str[-3] != ':':
             timestamp_str = timestamp_str[:-2] + ':' + timestamp_str[-2:]
        
        timestamp = datetime.fromisoformat(timestamp_str).strftime('%d-%b-%Y %H:%M')
        media_id = media_item['id']
        return f"{caption[:50]}... ({timestamp}) - ID: {media_id}"

    selected_media = st.selectbox("Choose a video to analyze", options=video_options, format_func=format_video_option)
    if selected_media:
        media_id = selected_media['id']
        col1, col2 = st.columns([1, 2])
        with col1:
            if selected_media.get('media_url'): st.video(selected_media['media_url'])
        with col2:
            with st.spinner("Fetching insights for this video..."):
                insights = st.session_state.api.get_media_insights(media_id)
            if insights.get("success"):
                data = {item['name']: item['values'][0]['value'] for item in insights['data']['data']}
                st.metric("❤️ Likes", f"{data.get('likes', 0):,}")
                st.metric("💬 Comments", f"{data.get('comments', 0):,}")
                st.metric("💾 Saves", f"{data.get('saved', 0):,}")
                st.metric("👀 Reach", f"{data.get('reach', 0):,}")
            else:
                st.error(f"Could not load insights. Reason: {insights.get('error')}")
    
    st.markdown("---")
    st.subheader("📈 Overall Engagement Over Time")
    df = pd.DataFrame(media_list)
    if not df.empty:
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df['total_engagement'] = df.get('like_count', 0) + df.get('comments_count', 0)
        fig = px.line(df, x='timestamp', y='total_engagement', title="Daily Engagement (Likes + Comments)")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No media data to plot.")

def render_scheduled_posts_tab():
    """Renders the 'Scheduled Posts' tab, handling both display and edit modes."""
    st.header("📅 Scheduled Posts Management")
    if 'editing_post_id' in st.session_state:
        render_edit_form()
    else:
        display_scheduled_posts()

def display_scheduled_posts():
    """Displays the list of currently scheduled single-use posts."""
    if st.button("🔄 Refresh Posts"): st.rerun()
    posts = st.session_state.scheduler.get_scheduled_posts() if st.session_state.scheduler else []
    if not posts:
        st.info("📭 No posts are currently scheduled."); return
    
    for post in sorted(posts, key=lambda p: p['scheduled_time']):
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.write(f"**Scheduled for:** {datetime.fromisoformat(post['scheduled_time']).strftime('%Y-%m-%d %H:%M %Z')}")
                st.caption(f"Caption: {post['caption'][:100]}...")
                st.write(f"**Status:** {post.get('status', 'scheduled').capitalize()}")
                if 'error' in post: st.error(f"Error: {post['error']}")
            with c2:
                if st.button("✏️ Edit", key=f"edit_{post['id']}", use_container_width=True):
                    st.session_state.editing_post_id = post['id']; st.rerun()
                if st.button("🗑️ Delete", key=f"delete_{post['id']}", use_container_width=True):
                    if st.session_state.scheduler.delete_scheduled_post(post['id']):
                        st.success("Post deleted."); st.rerun()
                    else: st.error("Failed to delete post.")

def render_edit_form():
    """Renders the form for editing a specific scheduled post."""
    post_id = st.session_state.editing_post_id
    posts = st.session_state.scheduler.get_scheduled_posts()
    post_to_edit = next((p for p in posts if p['id'] == post_id), None)
    if not post_to_edit:
        st.error("Post not found."); del st.session_state.editing_post_id; return
    
    st.subheader("✏️ Editing Scheduled Post")
    with st.form("edit_post_form"):
        new_caption = st.text_area("Caption", value=post_to_edit['caption'], height=150)
        current_dt = datetime.fromisoformat(post_to_edit['scheduled_time'])
        new_date = st.date_input("New Date", value=current_dt.date())
        new_time = st.time_input("New Time", value=current_dt.time(), step=timedelta(minutes=1))
        
        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                ist = pytz.timezone('Asia/Kolkata')
                full_datetime = ist.localize(datetime.combine(new_date, new_time))
                success = st.session_state.scheduler.update_scheduled_post(
                    post_id=post_id, new_caption=new_caption, new_datetime=full_datetime
                )
                if success:
                    st.success("✅ Post rescheduled!")
                    del st.session_state.editing_post_id; st.rerun()
                else: st.error("❌ Failed to update post.")
        with c2:
            if st.form_submit_button("❌ Cancel", use_container_width=True):
                del st.session_state.editing_post_id; st.rerun()

# --- Page-Level Rendering Functions (App Modes) ---

def render_login_page():
    """Renders the login page for PIN-based authentication."""
    st.title("🔐 Login")
    st.markdown("Please enter the PIN to access the post management dashboard.")
    pin_input = st.text_input("PIN", type="password", key="pin_input")
    if st.button("Login", use_container_width=True):
        if pin_input == st.session_state.config.app_pin:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("The PIN you entered is incorrect.")

def render_landing_page():
    """Renders the main landing page, acting as a navigation hub."""
    # --- FIX: Removed success message from here ---
    st.markdown("""
    <div class="main-header">
        <h1>Welcome to ReelPilot AI</h1>
        <p>What would you like to do today?</p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        with st.container(border=True):
            st.subheader("🤖 AI Account Analysis")
            st.write("Get a real-time summary and performance analysis for any public Instagram Business/Creator account.")
            if st.button("Analyze an Account", use_container_width=True, type="primary"):
                st.session_state.app_mode = 'analyze'; st.rerun()
    with col2:
        with st.container(border=True):
            st.subheader("🗓️ Manage & Schedule Posts")
            st.write("Access the dashboard to upload, schedule, and manage your own Instagram Reels.")
            if st.button("Manage My Posts", use_container_width=True, type="primary"):
                st.session_state.app_mode = 'manage'; st.rerun()

def render_analysis_page():
    """Renders the page for real-time AI-powered account analysis."""
    st.title("🔍 Real-Time Account Analysis")
    st.info(
        "**Important:** This tool uses the official Instagram Business Discovery API. "
        "It can only analyze **public Business or Creator accounts**. Analysis of personal accounts will fail."
    )
    if st.button("⬅️ Back to Home"):
        st.session_state.app_mode = 'landing'; st.rerun()

    is_ig_configured = st.session_state.config.is_configured()
    is_ai_configured = bool(st.session_state.config.google_api_key)
    
    if not (is_ig_configured and is_ai_configured):
        st.warning("⚠️ AI Analysis requires configuration. Please go to the **Manage My Posts** section, then to the **⚙️ Settings** tab to configure the application.")
        st.text_input("Enter Instagram Username to Analyze", placeholder="e.g., nasa", disabled=True)
        st.button("Analyze Account", use_container_width=True, type="primary", disabled=True)
        return

    username = st.text_input("Enter Instagram Username to Analyze", placeholder="e.g., nasa")
    if st.button("Analyze Account", use_container_width=True, type="primary"):
        if not username:
            st.error("Please enter a username.")
        else:
            with st.spinner(f"Fetching real-time data for @{username}..."):
                analysis = st.session_state.api.get_business_user_analysis(username)
            if analysis.get("success"):
                data = analysis["data"]
                st.subheader(f"Analysis for @{data['username']}")
                c1, c2, c3 = st.columns(3)
                c1.metric("Followers", f"{data.get('followers_count', 0):,}")
                c2.metric("Total Posts", f"{data.get('media_count', 'NA'):,}")
                c3.metric("Engagement Rate", f"{data['metrics']['engagement_rate_percent']:.2f}%", help="Based on last 10 posts")
                st.markdown("---")
                st.subheader("🤖 AI-Generated Summary")
                st.markdown(data['ai_summary'])
            else:
                st.error(f"Analysis Failed: {analysis.get('error')}")

# --- Main Application Logic ---

def main():
    """
    Main function to control the application flow based on the current app mode.
    """
    if st.session_state.app_mode == 'landing':
        render_landing_page()
    elif st.session_state.app_mode == 'analyze':
        render_analysis_page()
    elif st.session_state.app_mode == 'manage':
        # Check for PIN protection if enabled
        if st.session_state.config.app_pin and not st.session_state.get("authenticated"):
            render_login_page()
        else:
            render_sidebar()
            render_main_dashboard()

if __name__ == "__main__":
    main()
