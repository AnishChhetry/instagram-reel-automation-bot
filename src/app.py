import streamlit as st
import os
import json
import uuid
import pandas as pd
from datetime import datetime, timedelta, time
from pathlib import Path
import plotly.express as px
import numpy as np
import pytz

from instagram_api import InstagramAPI
from scheduler import ReelScheduler
from video_processor import VideoProcessor
from config import Config

st.set_page_config(
    page_title="Instagram Reel Pro Automation",
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
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'config' not in st.session_state:
    st.session_state.config = Config()
if 'api' not in st.session_state:
    st.session_state.api = None
if 'scheduler' not in st.session_state:
    st.session_state.scheduler = None

def initialize_components():
    """Initializes components if the app is configured."""
    config = st.session_state.config
    is_configured = config.is_configured()
    
    if is_configured:
        if st.session_state.api is None:
            st.session_state.api = InstagramAPI(config)
        if st.session_state.scheduler is None:
            st.session_state.scheduler = ReelScheduler()
    return is_configured

def render_sidebar():
    st.sidebar.markdown("### ⚙️ Automation Controls")
    is_configured = st.session_state.config.is_configured()
    
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

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🚀 Quick Actions")
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()
    if st.sidebar.button("⚡ Test API Connection", use_container_width=True, disabled=not is_configured):
        test_api_connection()

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📊 System Status")
    if is_configured and st.session_state.api:
        st.sidebar.metric("API Status", "✅ Connected")
        st.sidebar.metric("Scheduled Posts", st.session_state.scheduler.get_scheduler_status().get('total_posts', 0))
        limit_info = st.session_state.api.get_content_publishing_limit()
        if limit_info.get('success') and 'data' in limit_info and limit_info['data']:
            usage = limit_info['data']['data'][0].get('quota_usage', 'N/A')
            st.sidebar.metric("Daily API Posts Used", usage)
    else:
        st.sidebar.metric("API Status", "❌ Disconnected")

def test_api_connection():
    with st.spinner("Testing API connection..."):
        result = st.session_state.api.test_connection()
        if result["success"]:
            st.sidebar.success("✅ API Connection Successful")
        else:
            st.sidebar.error(f"❌ API Error: {result.get('error', 'Unknown error')}")

def render_main_dashboard():
    st.markdown("""
    <div class="main-header">
        <h1>🎬 Instagram Reel Pro Automation</h1>
        <p>Manage, schedule, and analyze your Instagram presence</p>
    </div>
    """, unsafe_allow_html=True)

    tabs = ["📤 Upload & Schedule", "🔁 Recurring Post", "🚀 Performance", "📅 Scheduled Posts", "👤 Account Details", "⚙️ Settings"]
    tab_upload, tab_recurring, tab_performance, tab_scheduled, tab_details, tab_settings = st.tabs(tabs)
    
    is_configured = initialize_components()

    with tab_settings:
        render_settings_tab()

    if not is_configured:
        st.warning("⚠️ API not configured. Please go to the Settings tab.")
        return

    with st.spinner("Loading dashboard data..."):
        account_info = st.session_state.api.test_connection()
        media_info = st.session_state.api.get_user_media(limit=25)
        insights_info = st.session_state.api.get_account_insights(period='days_28')

    total_posts, followers, reach, engagement_rate = 'N/A', 'N/A', 'N/A', 'N/A'
    if account_info.get('success'):
        data = account_info['data']
        total_posts, followers = data.get('media_count', 'N/A'), data.get('followers_count', 0)
    if insights_info.get('success') and 'data' in insights_info and insights_info['data'].get('data'):
        for metric in insights_info['data']['data']:
            if metric['name'] == 'reach' and metric['values']: reach = f"{metric['values'][0].get('value', 0):,}"
    if media_info.get('success') and 'data' in media_info and followers and followers > 0:
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

    with tab_upload: render_upload_tab()
    with tab_recurring: render_recurring_post_tab()
    with tab_performance: render_performance_tab(media_info)
    with tab_scheduled: render_scheduled_posts_tab()
    with tab_details: render_account_details_tab()

def render_settings_tab():
    st.header("⚙️ Settings & Configuration")
    with st.form("settings_form"):
        st.subheader("🔧 Instagram API Credentials")
        config = st.session_state.config
        access_token = st.text_input("Access Token", value=config.access_token or "", type="password")
        app_id = st.text_input("App ID", value=config.app_id or "")
        app_secret = st.text_input("App Secret", value=config.app_secret or "", type="password")
        instagram_id = st.text_input("Instagram Account ID", value=config.instagram_account_id or "")
        
        st.subheader("🔗 Ngrok Configuration")
        ngrok_token = st.text_input("Ngrok Authtoken", value=config.ngrok_authtoken or "", type="password")
        
        if st.form_submit_button("💾 Save Configuration", type="primary", use_container_width=True):
            config_data = {"ACCESS_TOKEN": access_token, "APP_ID": app_id, "APP_SECRET": app_secret, "INSTAGRAM_ACCOUNT_ID": instagram_id, "NGROK_AUTHTOKEN": ngrok_token}
            if config.save_config(config_data):
                st.success("✅ Configuration saved! Reloading application...")
                st.session_state.config = Config()
                st.session_state.api = None
                st.session_state.scheduler = None
                st.rerun()
            else:
                st.error("❌ Failed to save configuration file.")

def render_account_details_tab():
    st.header("👤 Instagram Account Details")
    with st.spinner("Fetching account details..."):
        account_info = st.session_state.api.test_connection()
    if account_info.get('success'):
        st.subheader("Account Overview")
        st.json(account_info['data'])
    else:
        st.error(f"Could not fetch account details: {account_info.get('error')}")

def render_upload_tab():
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
                schedule_type = st.session_state.schedule_type
                if not caption: st.error("❌ A caption is required.")
                else:
                    schedule_datetime = None
                    if schedule_type == "⏰ Schedule for Later":
                        ist = pytz.timezone('Asia/Kolkata')
                        selected_date = st.session_state.schedule_date
                        selected_time = st.session_state.schedule_time
                        naive_datetime = datetime.combine(selected_date, selected_time)
                        schedule_datetime = ist.localize(naive_datetime)
                        if schedule_datetime < datetime.now(ist) + timedelta(minutes=1):
                            st.error("❌ Scheduled time must be at least one minute in the future.")
                            return
                    process_reel_upload(uploaded_file, caption, schedule_type, schedule_datetime)

def process_reel_upload(uploaded_file, caption, schedule_type, schedule_datetime=None):
    try:
        with st.spinner("Processing video..."):
            vp = VideoProcessor(st.session_state.config)
            video_data = vp.process_uploaded_video(uploaded_file)
        if schedule_type == "📤 Post Now":
            with st.spinner("Posting reel to Instagram..."):
                result = st.session_state.api.post_reel(video_data['path'], caption)
            if result.get('success'):
                st.success(f"✅ Reel posted! Media ID: {result.get('media_id')}")
            else:
                st.error(f"❌ Failed to post reel: {result.get('error')}")
        else:
            post_data = {"id": str(uuid.uuid4()), "video_path": video_data['path'], "caption": caption, "scheduled_time": schedule_datetime.isoformat()}
            st.session_state.scheduler.schedule_post(post_data)
            st.success(f"✅ Reel scheduled for {schedule_datetime.strftime('%Y-%m-%d at %H:%M %Z')}!")
    except Exception as e:
        st.error(f"❌ An error occurred: {e}")

def render_recurring_post_tab():
    st.header("🔁 Recurring Daily Post")
    st.info("Set one video to be posted automatically at three specific times every day.")
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
        with st.form("recurring_form"):
            video_file = st.file_uploader("Choose a video for recurring posts", type=st.session_state.config.allowed_video_formats)
            caption = st.text_area("Recurring Caption", height=100)
            st.write("**Select three times of the day (IST):**")
            c1, c2, c3 = st.columns(3)
            time1 = c1.time_input("Time 1", value=time(9, 0))
            time2 = c2.time_input("Time 2", value=time(14, 0))
            time3 = c3.time_input("Time 3", value=time(20, 0))
            submitted = st.form_submit_button("🚀 Start Recurring Schedule", use_container_width=True)
            if submitted:
                if not video_file: st.error("You must upload a video file.")
                elif not caption: st.error("A caption is required.")
                else:
                    with st.spinner("Processing video and setting schedule..."):
                        try:
                            vp = VideoProcessor(st.session_state.config)
                            video_data = vp.process_uploaded_video(video_file)
                            st.session_state.scheduler.schedule_recurring_post(
                                video_path=video_data['path'], caption=caption, times=[time1, time2, time3]
                            )
                            st.success("Recurring schedule set successfully!"); st.rerun()
                        except Exception as e:
                            st.error(f"An error occurred: {e}")

# In app.py, replace the render_performance_tab function

def render_performance_tab(media_info):
    st.header("🚀 Video Performance Insights")
    st.write("Select one of your recent videos to view its detailed performance metrics.")

    if not media_info.get("success"):
        st.error("Could not fetch your recent media to analyze. Please check your API connection.")
        return

    media_list = media_info.get("data", {}).get("data", [])
    video_options = [m for m in media_list if m.get("media_type") in ["VIDEO", "REELS"]]

    if not video_options:
        st.warning("You don't have any recent videos/reels to analyze.")
        return

    option_dict = {
        f"{m.get('caption', 'No caption')[:50]}... ({datetime.fromisoformat(m['timestamp']).strftime('%d-%b-%Y')})": m
        for m in video_options
    }
    
    selected_option_key = st.selectbox("Choose a video to analyze", options=option_dict.keys())

    if selected_option_key:
        selected_media = option_dict[selected_option_key]
        media_id = selected_media['id']
        media_url = selected_media.get('media_url')

        col1, col2 = st.columns([1, 2])
        with col1:
            if media_url:
                st.video(media_url)
        
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
                # --- ENHANCED ERROR REPORTING ---
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
    st.header("📅 Scheduled Posts Management")
    if 'editing_post_id' in st.session_state: render_edit_form()
    else: display_scheduled_posts()

def display_scheduled_posts():
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
    post_id = st.session_state.editing_post_id
    posts = st.session_state.scheduler.get_scheduled_posts()
    post_to_edit = next((p for p in posts if p['id'] == post_id), None)
    if not post_to_edit:
        st.error("Post not found."); del st.session_state.editing_post_id; return
    st.subheader(f"✏️ Editing Scheduled Post")
    with st.form("edit_post_form"):
        new_caption = st.text_area("Caption", value=post_to_edit['caption'], height=150)
        current_dt = datetime.fromisoformat(post_to_edit['scheduled_time'])
        new_date = st.date_input("New Date", value=current_dt.date())
        new_time = st.time_input("New Time", value=current_dt.time())
        c1, c2 = st.columns(2)
        with c1:
            if st.form_submit_button("💾 Save Changes", type="primary", use_container_width=True):
                ist = pytz.timezone('Asia/Kolkata')
                full_datetime = ist.localize(datetime.combine(new_date, new_time))
                success = st.session_state.scheduler.update_scheduled_post(
                    post_id=post_id, new_caption=new_caption, new_datetime=full_datetime
                )
                if success:
                    st.success(f"✅ Post rescheduled!")
                    del st.session_state.editing_post_id; st.rerun()
                else: st.error("❌ Failed to update post.")
        with c2:
            if st.form_submit_button("❌ Cancel", use_container_width=True):
                del st.session_state.editing_post_id; st.rerun()

def main():
    render_main_dashboard()
    render_sidebar()

if __name__ == "__main__":
    main()
