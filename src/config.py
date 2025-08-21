import os
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """Enhanced configuration management"""

    def __init__(self, env_file: str = "../config/.env"):
        self.env_file = env_file
        self._load_config()

    def _load_config(self):
        """Load configuration from environment variables"""
        if os.path.exists(self.env_file):
            load_dotenv(self.env_file)

        # Instagram API configuration
        self.access_token = os.getenv("ACCESS_TOKEN")
        self.app_id = os.getenv("APP_ID") 
        self.app_secret = os.getenv("APP_SECRET")
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN")

        # Application settings
        self.max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
        self.allowed_video_formats = os.getenv("ALLOWED_VIDEO_FORMATS", "mp4,mov,avi").split(",")
        self.video_storage_path = os.getenv("VIDEO_STORAGE_PATH", "../data/videos")
        self.temp_storage_path = os.getenv("TEMP_STORAGE_PATH", "../data/temp")

        # Logging
        self.log_file = os.getenv("LOG_FILE", "../data/logs/app.log")

        self._create_directories()

    def _create_directories(self):
        """Create necessary directories"""
        directories = [
            self.video_storage_path,
            self.temp_storage_path,
            os.path.dirname(self.log_file),
            "../data/scheduled_posts",
            "../data/logs"
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def is_configured(self) -> bool:
        """Check if all required configuration is present"""
        required_fields = [
            self.access_token,
            self.app_id,
            self.app_secret,
            self.instagram_account_id,
            self.ngrok_authtoken
        ]
        return all(field is not None and field.strip() != "" for field in required_fields)

    def save_config(self, config_data: dict):
        """Save configuration to .env file"""
        try:
            os.makedirs(os.path.dirname(self.env_file), exist_ok=True)
            with open(self.env_file, "w") as f:
                for key, value in config_data.items():
                    f.write(f"{key}={value}\n")
            return True
        except Exception as e:
            print(f"Error saving configuration: {str(e)}")
            return False

    # --- ADDED BACK: Missing helper methods ---

    def validate_video_file(self, filename: str) -> bool:
        """Validate if file is an allowed video format"""
        file_ext = Path(filename).suffix.lower().lstrip('.')
        return file_ext in self.allowed_video_formats

    def get_video_path(self, filename: str) -> str:
        """Get full path for video storage"""
        return os.path.join(self.video_storage_path, filename)

    def get_temp_path(self, filename: str) -> str:
        """Get full path for temporary storage"""
        return os.path.join(self.temp_storage_path, filename)
