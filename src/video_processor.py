import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
import logging

class VideoProcessor:
    """Enhanced video processing with UI integration"""

    def __init__(self, config=None):
        from config import Config
        self.config = config or Config()

        # Set up logging
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO)

    def process_uploaded_video(self, uploaded_file) -> Dict[str, Any]:
        """Process video uploaded through Streamlit"""
        try:
            # Validate file
            validation_result = self._validate_video(uploaded_file)
            if not validation_result["valid"]:
                raise Exception(validation_result["error"])

            # Generate unique filename
            file_extension = Path(uploaded_file.name).suffix.lower()
            unique_filename = f"{uuid.uuid4()}{file_extension}"

            # Save to permanent storage
            video_path = self.config.get_video_path(unique_filename)

            # Ensure directory exists
            os.makedirs(os.path.dirname(video_path), exist_ok=True)

            # Write uploaded file to disk
            with open(video_path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            self.logger.info(f"Video saved to {video_path}")

            # Get video info
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
        """Validate uploaded video file"""
        try:
            # Check file size
            size_mb = uploaded_file.size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                return {
                    "valid": False,
                    "error": f"File size ({size_mb:.1f}MB) exceeds limit ({self.config.max_file_size_mb}MB)"
                }

            # Check file format
            if not self.config.validate_video_file(uploaded_file.name):
                return {
                    "valid": False,
                    "error": f"File format not supported. Allowed formats: {', '.join(self.config.allowed_video_formats)}"
                }

            # Check if file is empty
            if uploaded_file.size == 0:
                return {
                    "valid": False,
                    "error": "File is empty"
                }

            return {"valid": True}

        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get basic video information"""
        info = {}

        try:
            # Basic file info
            file_stat = os.stat(video_path)
            info.update({
                "duration": None,  # Would need moviepy for actual duration
                "fps": None,
                "width": None,
                "height": None,
                "aspect_ratio": None,
                "file_size": file_stat.st_size,
                "created_at": file_stat.st_ctime
            })

        except Exception as e:
            self.logger.warning(f"Could not extract video info: {str(e)}")
            info = {
                "duration": None,
                "fps": None,
                "width": None,
                "height": None,
                "aspect_ratio": None
            }

        return info

    def get_video_stats(self) -> Dict[str, Any]:
        """Get statistics about stored videos"""
        try:
            video_dir = Path(self.config.video_storage_path)
            if not video_dir.exists():
                return {"total_videos": 0, "total_size_mb": 0}

            video_files = list(video_dir.glob("*"))
            total_size = sum(f.stat().st_size for f in video_files if f.is_file())

            return {
                "total_videos": len(video_files),
                "total_size_mb": round(total_size / (1024 * 1024), 2)
            }

        except Exception as e:
            self.logger.error(f"Error getting video stats: {str(e)}")
            return {"total_videos": 0, "total_size_mb": 0, "error": str(e)}
