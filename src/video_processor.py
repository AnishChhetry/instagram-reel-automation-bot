# -*- coding: utf-8 -*-
"""
Video processing utility for ReelPilot AI.

This module provides the VideoProcessor class, which handles all aspects of
video file management, including validation of uploaded files, saving them to
appropriate temporary or permanent storage locations, and extracting basic
file metadata.
"""

import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import logging

class VideoProcessor:
    """
    Handles video file validation, storage, and metadata extraction.

    This class provides a clean interface for processing video files uploaded
    via the Streamlit UI, ensuring they meet size and format requirements before
    being saved to the filesystem.

    Attributes:
        config: An instance of the Config class containing file settings.
        logger: A configured logger for recording processing events.
    """

    def __init__(self, config=None):
        """
        Initializes the VideoProcessor.

        Args:
            config (Config, optional): A configuration object. If not provided,
                                       a new one will be instantiated.
        """
        # Lazy import to avoid circular dependency issues if config needs this module.
        from config import Config
        self.config = config or Config()

        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    def process_uploaded_video(self, uploaded_file, is_temporary: bool = False) -> Dict[str, Any]:
        """
        Processes a video file uploaded via Streamlit.

        Validates the file against configured limits, generates a unique
        filename, and saves it to either a temporary or permanent location based
        on the `is_temporary` flag.

        Args:
            uploaded_file: The file-like object from a Streamlit file_uploader.
            is_temporary (bool): If True, saves to the temp directory for
                                 immediate posting. If False, saves to the
                                 permanent video storage for scheduling.

        Returns:
            Dict[str, Any]: A dictionary containing details of the processed
                            video, including its new path and metadata.

        Raises:
            Exception: If validation fails or a file I/O error occurs.
        """
        try:
            validation_result = self._validate_video(uploaded_file)
            if not validation_result["valid"]:
                raise Exception(validation_result["error"])

            # Create a unique filename to prevent collisions.
            file_extension = Path(uploaded_file.name).suffix.lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"

            # Determine the correct storage path.
            if is_temporary:
                video_path = self.config.get_temp_path(unique_filename)
            else:
                video_path = self.config.get_video_path(unique_filename)

            os.makedirs(os.path.dirname(video_path), exist_ok=True)

            # Write the uploaded file's buffer to the designated path.
            with open(video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            self.logger.info(f"Video saved to {video_path}")
            video_info = self._get_video_info(video_path)

            return {
                "path": video_path,
                "filename": unique_filename,
                "original_name": uploaded_file.name,
                "size_bytes": uploaded_file.size,
                "size_mb": round(uploaded_file.size / (1024 * 1024), 2),
                **video_info
            }

        except Exception as e:
            self.logger.error(f"Error processing video: {str(e)}")
            raise e

    def _validate_video(self, uploaded_file) -> Dict[str, Any]:
        """
        Validates an uploaded video file against size and format constraints.

        Args:
            uploaded_file: The file-like object from Streamlit.

        Returns:
            Dict[str, Any]: A dictionary with a 'valid' boolean and an 'error'
                            message if validation fails.
        """
        try:
            if uploaded_file.size / (1024 * 1024) > self.config.max_file_size_mb:
                return {"valid": False, "error": f"File size exceeds limit ({self.config.max_file_size_mb}MB)"}
            if not self.config.validate_video_file(uploaded_file.name):
                return {"valid": False, "error": f"Unsupported format. Allowed: {', '.join(self.config.allowed_video_formats)}"}
            if uploaded_file.size == 0:
                return {"valid": False, "error": "File is empty"}
            return {"valid": True}
        except Exception as e:
            return {"valid": False, "error": f"Validation error: {str(e)}"}

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """
        Extracts basic filesystem metadata from a video file.

        Args:
            video_path (str): The absolute path to the video file.

        Returns:
            Dict[str, Any]: A dictionary with file size and creation time,
                            or an empty dict on failure.
        """
        try:
            file_stat = os.stat(video_path)
            return {"file_size": file_stat.st_size, "created_at": file_stat.st_ctime}
        except Exception as e:
            self.logger.warning(f"Could not extract video info: {str(e)}")
            return {}

    def get_video_stats(self) -> Dict[str, Any]:
        """
        Calculates statistics about all videos in the permanent storage directory.

        Returns:
            Dict[str, Any]: A dictionary containing the total number of videos
                            and their combined size in megabytes.
        """
        try:
            video_dir = Path(self.config.video_storage_path)
            if not video_dir.exists():
                return {"total_videos": 0, "total_size_mb": 0}
            
            video_files = [f for f in video_dir.glob("*") if f.is_file()]
            total_size = sum(f.stat().st_size for f in video_files)
            
            return {
                "total_videos": len(video_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }
        except Exception as e:
            self.logger.error(f"Error getting video stats: {str(e)}")
            return {"total_videos": 0, "total_size_mb": 0, "error": str(e)}
