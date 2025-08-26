# -*- coding: utf-8 -*-
"""
Configuration management for the ReelPilot AI application.

This module defines the Config class, which is responsible for loading,
managing, and saving all application settings. It uses python-dotenv to
load credentials from a .env file and provides methods for path management,
validation, and ensuring that critical directories exist.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

class Config:
    """
    Handles application configuration with robust, absolute path management.

    This class centralizes access to all configuration variables, such as API
    keys, file paths, and application settings. It ensures all file paths are
    resolved as absolute paths relative to the project root, preventing issues
    with the current working directory.

    Attributes:
        project_root (Path): The absolute path to the project's root directory.
        env_file (Path): The absolute path to the .env configuration file.
        access_token (str): Instagram Graph API access token.
        app_id (str): Meta App ID.
        app_secret (str): Meta App Secret.
        instagram_account_id (str): The target Instagram Account ID.
        ngrok_authtoken (str): Ngrok authentication token.
        app_pin (str): Optional PIN for securing the management dashboard.
        google_api_key (str): API key for Google AI (Gemini).
        video_storage_path (str): Absolute path to the permanent video storage.
        temp_storage_path (str): Absolute path to the temporary video storage.
        log_file (str): Absolute path to the application log file.
        max_file_size_mb (int): Maximum allowed video upload size in megabytes.
        allowed_video_formats (list): A list of allowed video file extensions.
    """

    def __init__(self):
        """Initializes the Config class by resolving paths and loading settings."""
        # Determine the project root directory based on this file's location.
        # This makes path resolution independent of where the script is run from.
        src_dir = Path(__file__).resolve().parent
        self.project_root = src_dir.parent
        self.env_file = self.project_root / "config" / ".env"
        
        self._load_config()

    def _make_path_absolute(self, path_str: str) -> str:
        """
        Converts a relative path string from the config to an absolute path.

        If the path is already absolute, it is returned unchanged. Otherwise,
        it's joined with the project root directory.

        Args:
            path_str (str): The path string to convert.

        Returns:
            str: The absolute path.
        """
        if os.path.isabs(path_str):
            return path_str
        return str(self.project_root / path_str)

    def _load_config(self):
        """
        Loads configuration from the .env file into instance attributes.
        
        It uses default values for non-critical settings if they are not
        specified in the .env file.
        """
        if self.env_file.exists():
            load_dotenv(self.env_file)

        # Load Instagram API and other service credentials from environment.
        self.access_token = os.getenv("ACCESS_TOKEN")
        self.app_id = os.getenv("APP_ID") 
        self.app_secret = os.getenv("APP_SECRET")
        self.instagram_account_id = os.getenv("INSTAGRAM_ACCOUNT_ID")
        self.ngrok_authtoken = os.getenv("NGROK_AUTHTOKEN")
        self.app_pin = os.getenv("APP_PIN") 
        self.google_api_key = os.getenv("GOOGLE_API_KEY")

        # Load application settings, ensuring all paths are absolute.
        self.video_storage_path = self._make_path_absolute(os.getenv("VIDEO_STORAGE_PATH", "data/videos"))
        self.temp_storage_path = self._make_path_absolute(os.getenv("TEMP_STORAGE_PATH", "data/temp"))
        self.log_file = self._make_path_absolute(os.getenv("LOG_FILE", "data/logs/app.log"))

        # Load other application parameters with defaults.
        self.max_file_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "200"))
        self.allowed_video_formats = os.getenv("ALLOWED_VIDEO_FORMATS", "mp4,mov,avi").split(",")

        self._create_directories()

    def _create_directories(self):
        """
        Ensures that all necessary data and log directories exist on startup.
        """
        directories = [
            self.video_storage_path,
            self.temp_storage_path,
            os.path.dirname(self.log_file),
            self.project_root / "data" / "scheduled_posts",
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)

    def is_configured(self) -> bool:
        """
        Checks if all required Instagram API credentials are present.

        Returns:
            bool: True if the essential configuration is set, False otherwise.
        """
        required_fields = [
            self.access_token, self.app_id, self.app_secret,
            self.instagram_account_id, self.ngrok_authtoken
        ]
        return all(field is not None and field.strip() != "" for field in required_fields)

    def save_config(self, config_data: dict) -> bool:
        """
        Saves the provided configuration dictionary to the .env file.

        This method overwrites the existing .env file. It wraps values in
        quotes to handle special characters and skips empty values.

        Args:
            config_data (dict): A dictionary of configuration key-value pairs.

        Returns:
            bool: True on successful save, False on failure.
        """
        try:
            self.env_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.env_file, "w") as f:
                for key, value in config_data.items():
                    if value:
                        f.write(f'{key}="{value}"\n')
            return True
        except Exception as e:
            print(f"Error saving configuration: {str(e)}")
            return False

    def validate_video_file(self, filename: str) -> bool:
        """
        Validates if a given filename has an allowed video format.

        Args:
            filename (str): The name of the file to validate.

        Returns:
            bool: True if the format is allowed, False otherwise.
        """
        file_ext = Path(filename).suffix.lower().lstrip('.')
        return file_ext in self.allowed_video_formats

    def get_video_path(self, filename: str) -> str:
        """
        Constructs the full absolute path for storing a permanent video file.

        Args:
            filename (str): The name of the video file.

        Returns:
            str: The full path for the video in the storage directory.
        """
        return os.path.join(self.video_storage_path, filename)

    def get_temp_path(self, filename: str) -> str:
        """
        Constructs the full absolute path for storing a temporary video file.

        Args:
            filename (str): The name of the video file.

        Returns:
            str: The full path for the video in the temporary directory.
        """
        return os.path.join(self.temp_storage_path, filename)
