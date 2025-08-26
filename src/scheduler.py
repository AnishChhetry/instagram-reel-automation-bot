# -*- coding: utf-8 -*-
"""
Core scheduling engine for ReelPilot AI.

This module defines the ReelScheduler class, which manages all background
posting tasks using APScheduler. It supports scheduling, updating, and deleting
both single-use and recurring posts. Job data and post metadata are persisted
to ensure reliability across application restarts.
"""

import json
import os
from datetime import datetime, time
from typing import Dict, Any, List, Optional
import logging
from pathlib import Path
import uuid

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from instagram_api import InstagramAPI
from config import Config

# --- Helper Functions ---

def _delete_video_file(path: str, logger: logging.Logger):
    """
    Safely deletes a video file from the filesystem.

    Args:
        path (str): The absolute path to the video file.
        logger (logging.Logger): The logger instance to record the operation.
    """
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Successfully deleted video file: {path}")
        except OSError as e:
            logger.error(f"Error deleting video file {path}: {e}")

def execute_post_task(post_data: Dict[str, Any]):
    """
    The target function executed by APScheduler for each post.

    This standalone function initializes its own API and Config instances to
    ensure it runs independently in a separate thread. It posts the reel and,
    on success, cleans up the associated video file for non-recurring posts.

    Args:
        post_data (Dict[str, Any]): A dictionary containing post details like
                                     video_path and caption.

    Returns:
        str: The media ID of the successfully posted reel.

    Raises:
        Exception: If the post fails, the exception is re-raised to be
                   caught by the APScheduler error listener.
    """
    post_id = post_data.get("id", f"recurring_{datetime.now().timestamp()}")
    logger = logging.getLogger("ReelSchedulerTask")
    logger.info(f"Executing post {post_id} via standalone task.")
    
    try:
        config = Config()
        api = InstagramAPI(config)
        video_path = post_data.get("video_path")
        
        if not video_path:
            raise ValueError("Task data is missing 'video_path'.")

        result = api.post_reel(video_path=video_path, caption=post_data["caption"])

        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error during post execution."))
        
        # On success, delete the video file for single-use posts to save space.
        if not post_id.startswith("recurring_"):
            _delete_video_file(video_path, logger)
            
        return result.get("media_id")

    except Exception as e:
        logger.error(f"Error executing post {post_id}: {str(e)}")
        raise e

# --- Main Scheduler Class ---

class ReelScheduler:
    """
    Manages scheduling, execution, and tracking of Instagram posts.

    This class encapsulates a BackgroundScheduler instance, persisting jobs in a
    SQLite database. It handles the lifecycle of scheduled posts, including
    creation, updates, deletion, and status tracking in a JSON file.

    Attributes:
        db_path (str): Path to the SQLite database for the job store.
        posts_file (str): Path to the JSON file for tracking post metadata.
        logger: A configured logger for scheduler-specific events.
        scheduler (BackgroundScheduler): The core APScheduler instance.
        scheduled_posts (Dict): A dictionary holding metadata of all posts.
    """

    def __init__(self, db_path: str = "../data/scheduler.db"):
        """
        Initializes the ReelScheduler.

        Args:
            db_path (str): The path to the scheduler's database file.
        """
        self.db_path = db_path
        self.posts_file = "../data/scheduled_posts/posts.json"
        self.recurring_config_file = "../data/scheduled_posts/recurring_post.json"
        self.logs_dir = "../data/logs"

        # Ensure necessary directories exist.
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.posts_file), exist_ok=True)
        os.makedirs(self.logs_dir, exist_ok=True)

        self.logger = self._setup_logging()
        self.scheduled_posts = self._load_posts()
        self.scheduler = self._setup_scheduler()

        if not self.scheduler.running:
            self.scheduler.start()
            self.logger.info("Scheduler started successfully")
            self._reschedule_recurring_jobs_from_config()

    def _setup_logging(self) -> logging.Logger:
        """Configures a dedicated logger for the scheduler."""
        logger = logging.getLogger("ReelScheduler")
        logger.setLevel(logging.INFO)
        log_file = os.path.join(self.logs_dir, "scheduler.log")
        file_handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(file_handler)
        return logger

    def _setup_scheduler(self) -> BackgroundScheduler:
        """Configures and returns a BackgroundScheduler instance."""
        jobstores = {'default': SQLAlchemyJobStore(url=f'sqlite:///{self.db_path}')}
        executors = {'default': ThreadPoolExecutor(20)}
        job_defaults = {'coalesce': False, 'max_instances': 3, 'misfire_grace_time': 300}
        
        scheduler = BackgroundScheduler(jobstores=jobstores, executors=executors, job_defaults=job_defaults, timezone='Asia/Kolkata')
        
        # Add listeners to track job outcomes.
        scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        return scheduler

    def _job_executed_listener(self, event):
        """Callback for successfully executed jobs."""
        if not event.job_id.startswith("recurring_"):
            self.logger.info(f"Job {event.job_id} executed. Media ID: {event.retval}")
            self._update_post_status(event.job_id, "completed", media_id=event.retval)
        else:
            self.logger.info(f"Recurring job {event.job_id} executed successfully.")

    def _job_error_listener(self, event):
        """Callback for failed jobs."""
        if not event.job_id.startswith("recurring_"):
            self.logger.error(f"Job {event.job_id} failed: {event.exception}")
            self._update_post_status(event.job_id, "failed", str(event.exception))
        else:
            self.logger.error(f"Recurring job {event.job_id} failed: {event.exception}")

    def _load_posts(self) -> Dict[str, Any]:
        """Loads post metadata from the JSON tracking file."""
        try:
            if os.path.exists(self.posts_file):
                with open(self.posts_file, 'r') as f: return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading posts: {str(e)}")
            return {}

    def _save_posts(self):
        """Saves the current post metadata to the JSON tracking file."""
        try:
            with open(self.posts_file, 'w') as f: json.dump(self.scheduled_posts, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving posts: {str(e)}")

    def schedule_post(self, post_data: Dict[str, Any]) -> str:
        """
        Schedules a new single-use post.

        Args:
            post_data (Dict[str, Any]): Dictionary with post details.

        Returns:
            str: The unique ID of the scheduled post.
        """
        try:
            post_id = post_data.get("id", str(uuid.uuid4()))
            scheduled_time = datetime.fromisoformat(post_data["scheduled_time"])
            self.scheduler.add_job(func=execute_post_task, trigger=DateTrigger(run_date=scheduled_time), args=[post_data], id=post_id, replace_existing=True)
            post_data["status"] = "scheduled"
            self.scheduled_posts[post_id] = post_data
            self._save_posts()
            self.logger.info(f"Post {post_id} scheduled for {scheduled_time}")
            return post_id
        except Exception as e:
            self.logger.error(f"Error scheduling post: {str(e)}")
            raise e
            
    def _reschedule_recurring_jobs_from_config(self):
        """Reschedules recurring jobs from config on application startup."""
        config = self.get_recurring_schedule()
        if config:
            self.logger.info("Found recurring schedule config, applying on startup.")
            self.schedule_recurring_post(
                caption=config["caption"],
                times=[time.fromisoformat(t) for t in config["times"]],
                video_path=config.get("video_path")
            )

    def get_recurring_schedule(self) -> Optional[Dict[str, Any]]:
        """Retrieves the current recurring schedule configuration."""
        try:
            if os.path.exists(self.recurring_config_file):
                with open(self.recurring_config_file, 'r') as f: return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Error loading recurring config: {e}")
            return None

    def cancel_recurring_posts(self):
        """Cancels all recurring jobs and deletes the associated video and config."""
        self.logger.info("Attempting to cancel all recurring posts.")
        recurring_config = self.get_recurring_schedule()
        if recurring_config:
            _delete_video_file(recurring_config.get("video_path"), self.logger)
        
        for job in self.scheduler.get_jobs():
            if job.id.startswith("recurring_"):
                self.scheduler.remove_job(job.id)
                self.logger.info(f"Removed recurring job: {job.id}")
        if os.path.exists(self.recurring_config_file):
            os.remove(self.recurring_config_file)
            self.logger.info("Removed recurring post config file.")

    def schedule_recurring_post(self, caption: str, times: List[time], video_path: str):
        """
        Sets up a new daily recurring post schedule.

        This cancels any existing recurring schedule before creating new ones.

        Args:
            caption (str): The caption for the recurring posts.
            times (List[time]): A list of `time` objects for daily posting.
            video_path (str): The path to the video file to be posted.
        """
        self.cancel_recurring_posts()
        if not video_path:
            raise ValueError("video_path must be provided for recurring posts.")
        
        post_data = {"caption": caption, "video_path": video_path}
        for i, t in enumerate(times):
            job_id = f"recurring_{i}"
            self.scheduler.add_job(
                func=execute_post_task,
                trigger=CronTrigger(hour=t.hour, minute=t.minute, timezone='Asia/Kolkata'),
                args=[post_data], id=job_id, replace_existing=True
            )
            self.logger.info(f"Scheduled recurring job {job_id} for {t.strftime('%H:%M')} daily.")
        
        config_to_save = {
            "caption": caption, "times": [t.isoformat() for t in times],
            "video_path": video_path, "last_updated": datetime.now().isoformat()
        }
        with open(self.recurring_config_file, 'w') as f:
            json.dump(config_to_save, f, indent=2)

    def update_scheduled_post(self, post_id: str, new_caption: str, new_datetime: datetime) -> bool:
        """
        Updates the caption and schedule time of an existing single-use post.

        Args:
            post_id (str): The ID of the post to update.
            new_caption (str): The new caption.
            new_datetime (datetime): The new scheduled time.

        Returns:
            bool: True on success, False on failure.
        """
        try:
            self.scheduler.modify_job(job_id=post_id, trigger=DateTrigger(run_date=new_datetime))
            if post_id in self.scheduled_posts:
                self.scheduled_posts[post_id]['caption'] = new_caption
                self.scheduled_posts[post_id]['scheduled_time'] = new_datetime.isoformat()
                self._save_posts()
                self.logger.info(f"Post {post_id} updated and rescheduled for {new_datetime}.")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error rescheduling post {post_id}: {e}")
            return False

    def _update_post_status(self, post_id: str, status: str, error_message: str = None, media_id: str = None):
        """Updates the status of a post in the tracking file."""
        if post_id in self.scheduled_posts:
            self.scheduled_posts[post_id]["status"] = status
            if error_message: self.scheduled_posts[post_id]["error"] = error_message
            if media_id: self.scheduled_posts[post_id]["media_id"] = media_id
            self._save_posts()
            
    def get_scheduled_posts(self) -> List[Dict[str, Any]]: 
        """Returns a list of all tracked single-use posts."""
        return list(self.scheduled_posts.values())
            
    def get_scheduler_status(self) -> Dict[str, Any]:
        """Returns a dictionary with the current status of the scheduler."""
        jobs = self.scheduler.get_jobs()
        return {
            "running": self.scheduler.running,
            "total_jobs": len(jobs),
            "total_posts": len(self.scheduled_posts),
            "next_run": min([j.next_run_time for j in jobs if j.next_run_time], default=None)
        }
        
    def pause_scheduler(self):
        """Pauses the execution of all scheduled jobs."""
        if self.scheduler.running: self.scheduler.pause(); self.logger.info("Scheduler paused")
        
    def resume_scheduler(self):
        """Resumes the execution of scheduled jobs."""
        if self.scheduler.running: self.scheduler.resume(); self.logger.info("Scheduler resumed")
        
    def delete_scheduled_post(self, post_id: str) -> bool:
        """
        Deletes a scheduled post and its associated video file.

        Args:
            post_id (str): The ID of the post to delete.

        Returns:
            bool: True on success, False on failure.
        """
        try:
            try: 
                self.scheduler.remove_job(post_id)
            except Exception as e:
                self.logger.warning(f"Could not remove job from APScheduler (may have already run): {e}")
                
            if post_id in self.scheduled_posts:
                post_to_delete = self.scheduled_posts[post_id]
                _delete_video_file(post_to_delete.get("video_path"), self.logger)
                
                del self.scheduled_posts[post_id]
                self._save_posts()
                self.logger.info(f"Post {post_id} deleted from tracking file.")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting post {post_id}: {str(e)}")
            return False
