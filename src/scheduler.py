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

# In scheduler.py, replace the execute_post_task function

def execute_post_task(post_data: Dict[str, Any]):
    """Executes a scheduled post from a local video file."""
    post_id = post_data.get("id", f"recurring_{datetime.now().timestamp()}")
    logger = logging.getLogger("ReelSchedulerTask")
    logger.info(f"Executing post {post_id} via standalone task.")
    
    try:
        config = Config()
        api = InstagramAPI(config)
        
        if "video_path" in post_data and post_data["video_path"]:
            result = api.post_reel(
                video_path=post_data["video_path"],
                caption=post_data["caption"]
            )
        else:
            raise ValueError("Task data is missing 'video_path'.")

        if not result.get("success"):
            raise Exception(result.get("error", "Unknown error during post execution."))
            
        return result.get("media_id")

    except Exception as e:
        logger.error(f"Error executing post {post_id}: {str(e)}")
        raise e

class ReelScheduler:
    def __init__(self, db_path: str = "../data/scheduler.db"):
        self.db_path = db_path
        self.posts_file = "../data/scheduled_posts/posts.json"
        self.recurring_config_file = "../data/scheduled_posts/recurring_post.json"
        self.logs_dir = "../data/logs"

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
        logger = logging.getLogger("ReelScheduler")
        logger.setLevel(logging.INFO)
        log_file = os.path.join(self.logs_dir, "scheduler.log")
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        if not logger.handlers:
            logger.addHandler(file_handler)
        return logger

    def _setup_scheduler(self) -> BackgroundScheduler:
        jobstores = {'default': SQLAlchemyJobStore(url=f'sqlite:///{self.db_path}')}
        executors = {'default': ThreadPoolExecutor(20)}
        job_defaults = {'coalesce': False, 'max_instances': 3, 'misfire_grace_time': 300}
        
        # --- KEY CHANGE: Set the timezone to IST ---
        scheduler = BackgroundScheduler(
            jobstores=jobstores, 
            executors=executors, 
            job_defaults=job_defaults, 
            timezone='Asia/Kolkata'
        )
        
        scheduler.add_listener(self._job_executed_listener, EVENT_JOB_EXECUTED)
        scheduler.add_listener(self._job_error_listener, EVENT_JOB_ERROR)
        return scheduler

    def _job_executed_listener(self, event):
        job_id = event.job_id
        if not job_id.startswith("recurring_"):
            media_id = event.retval
            self.logger.info(f"Job {job_id} executed successfully. Media ID: {media_id}")
            self._update_post_status(job_id, "completed", media_id=media_id)
        else:
            self.logger.info(f"Recurring job {job_id} executed successfully.")

    def _job_error_listener(self, event):
        job_id = event.job_id
        exception = event.exception
        if not job_id.startswith("recurring_"):
            self.logger.error(f"Job {job_id} failed with error: {str(exception)}")
            self._update_post_status(job_id, "failed", str(exception))
        else:
            self.logger.error(f"Recurring job {job_id} failed with error: {str(exception)}")

    def _load_posts(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.posts_file):
                with open(self.posts_file, 'r') as f: return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading posts: {str(e)}")
            return {}

    def _save_posts(self):
        try:
            with open(self.posts_file, 'w') as f: json.dump(self.scheduled_posts, f, indent=2)
        except Exception as e:
            self.logger.error(f"Error saving posts: {str(e)}")

    def schedule_post(self, post_data: Dict[str, Any]) -> str:
        try:
            post_id = post_data.get("id", str(uuid.uuid4()))
            scheduled_time = datetime.fromisoformat(post_data["scheduled_time"])
            self.scheduler.add_job(
                func=execute_post_task,
                trigger=DateTrigger(run_date=scheduled_time),
                args=[post_data], id=post_id, name=f"IG Post - {post_id}", replace_existing=True
            )
            post_data["status"] = "scheduled"
            post_data["scheduled_at"] = datetime.now().isoformat()
            self.scheduled_posts[post_id] = post_data
            self._save_posts()
            self.logger.info(f"Post {post_id} scheduled for {scheduled_time}")
            return post_id
        except Exception as e:
            self.logger.error(f"Error scheduling post: {str(e)}")
            raise e
            
    def _reschedule_recurring_jobs_from_config(self):
        config = self.get_recurring_schedule()
        if config:
            self.logger.info("Found recurring schedule config, applying on startup...")
            self.schedule_recurring_post(
                caption=config["caption"],
                times=[time.fromisoformat(t) for t in config["times"]],
                source_media_id=config.get("source_media_id"),
                video_path=config.get("video_path")
            )

    def get_recurring_schedule(self) -> Optional[Dict[str, Any]]:
        try:
            if os.path.exists(self.recurring_config_file):
                with open(self.recurring_config_file, 'r') as f: return json.load(f)
            return None
        except Exception as e:
            self.logger.error(f"Error loading recurring config: {e}")
            return None

    def cancel_recurring_posts(self):
        self.logger.info("Attempting to cancel all recurring posts.")
        for job in self.scheduler.get_jobs():
            if job.id.startswith("recurring_"):
                self.scheduler.remove_job(job.id)
                self.logger.info(f"Removed recurring job: {job.id}")
        if os.path.exists(self.recurring_config_file):
            os.remove(self.recurring_config_file)
            self.logger.info("Removed recurring post config file.")

    def schedule_recurring_post(self, caption: str, times: List[time], source_media_id: str = None, video_path: str = None):
        self.cancel_recurring_posts()
        if not source_media_id and not video_path:
            raise ValueError("Either source_media_id or video_path must be provided.")
        post_data = {"caption": caption, "source_media_id": source_media_id, "video_path": video_path}
        for i, t in enumerate(times):
            job_id = f"recurring_{i}"
            self.scheduler.add_job(
                func=execute_post_task,
                trigger=CronTrigger(hour=t.hour, minute=t.minute, timezone='Asia/Kolkata'),
                args=[post_data], id=job_id, name=f"Daily Recurring Post at {t.strftime('%H:%M')}", replace_existing=True
            )
            self.logger.info(f"Scheduled recurring job {job_id} for {t.strftime('%H:%M')} daily in IST.")
        config_to_save = {
            "caption": caption, "times": [t.isoformat() for t in times],
            "source_media_id": source_media_id, "video_path": video_path,
            "last_updated": datetime.now().isoformat()
        }
        with open(self.recurring_config_file, 'w') as f:
            json.dump(config_to_save, f, indent=2)

    # In scheduler.py, find this existing method:
    def update_scheduled_post(self, post_id: str, new_caption: str, new_datetime: datetime):
        try:
            self.scheduler.modify_job(job_id=post_id, trigger=DateTrigger(run_date=new_datetime))
            if post_id in self.scheduled_posts:
                self.scheduled_posts[post_id]['caption'] = new_caption
                self.scheduled_posts[post_id]['scheduled_time'] = new_datetime.isoformat()
                self.scheduled_posts[post_id]['updated_at'] = datetime.now().isoformat()
                self._save_posts()
                self.logger.info(f"Post {post_id} updated and rescheduled for {new_datetime}.")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error rescheduling post {post_id}: {e}")
            return False

    # vvv ADD THIS MISSING METHOD HERE vvv
    def _update_post_status(self, post_id: str, status: str, error_message: str = None, media_id: str = None):
        """Update post status in the internal JSON log."""
        if post_id in self.scheduled_posts:
            self.scheduled_posts[post_id]["status"] = status
            self.scheduled_posts[post_id]["updated_at"] = datetime.now().isoformat()
            if error_message:
                self.scheduled_posts[post_id]["error"] = error_message
            if media_id:
                self.scheduled_posts[post_id]["media_id"] = media_id
            self._save_posts()
    # ^^^ END OF NEW METHOD ^^^
            
    # Keep the rest of the methods (get_scheduled_posts, etc.) as they are
    def get_scheduled_posts(self) -> List[Dict[str, Any]]: 
        return list(self.scheduled_posts.values())
            
    # Keep the rest of the methods (get_scheduled_posts, get_scheduler_status, etc.) as they are
    def get_scheduled_posts(self) -> List[Dict[str, Any]]: return list(self.scheduled_posts.values())
    def get_scheduler_status(self) -> Dict[str, Any]:
        jobs = self.scheduler.get_jobs()
        status = {"running": self.scheduler.running, "total_jobs": len(jobs), "total_posts": len(self.scheduled_posts), "pending_posts": len([p for p in self.scheduled_posts.values() if p.get("status") == "scheduled"]), "completed_posts": len([p for p in self.scheduled_posts.values() if p.get("status") == "completed"]), "failed_posts": len([p for p in self.scheduled_posts.values() if p.get("status") == "failed"]), "next_run": min([job.next_run_time for job in jobs]) if jobs else None, "daily_posting_enabled": any(job.id == "daily_posting" for job in jobs)}
        return status
    def pause_scheduler(self):
        if self.scheduler.running: self.scheduler.pause(); self.logger.info("Scheduler paused")
    def resume_scheduler(self):
        if self.scheduler.running: self.scheduler.resume(); self.logger.info("Scheduler resumed")
    def delete_scheduled_post(self, post_id: str) -> bool:
        try:
            try: self.scheduler.remove_job(post_id)
            except: pass
            if post_id in self.scheduled_posts:
                del self.scheduled_posts[post_id]
                self._save_posts()
                self.logger.info(f"Post {post_id} deleted")
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error deleting post {post_id}: {str(e)}")
            return False