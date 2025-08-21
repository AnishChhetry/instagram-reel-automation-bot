import requests
import json
import time
import os
from typing import Dict, Any, Optional, List, Tuple
import logging
from pathlib import Path
from datetime import datetime, timedelta

import threading
import http.server
import socketserver
from pyngrok import ngrok, conf

class InstagramAPI:
    """Enhanced Instagram Graph API integration with analytics"""

    def __init__(self, config):
        self.access_token = config.access_token
        self.app_id = config.app_id
        self.app_secret = config.app_secret
        self.instagram_account_id = config.instagram_account_id
        self.base_url = "https://graph.facebook.com/v20.0"

        if config.ngrok_authtoken:
            conf.get_default().auth_token = config.ngrok_authtoken
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    def test_connection(self) -> Dict[str, Any]:
        """Test the API connection and permissions"""
        try:
            url = f"{self.base_url}/{self.instagram_account_id}"
            params = {
                "fields": "id,username,media_count,followers_count",
                "access_token": self.access_token
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}

    def _start_server_and_ngrok(self, video_path: str) -> Tuple[Optional[str], Any, Any]:
        """Starts a temporary web server and ngrok tunnel to expose a local video file."""
        try:
            port = 8000
            video_directory = os.path.dirname(video_path)
            video_filename = os.path.basename(video_path)

            class DirectoryHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=video_directory, **kwargs)

            httpd = socketserver.TCPServer(("", port), DirectoryHandler)
            server_thread = threading.Thread(target=httpd.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            self.logger.info(f"HTTP server started on port {port} for directory {video_directory}")

            public_tunnel = ngrok.connect(port, "http")
            public_url = f"{public_tunnel.public_url}/{video_filename}"
            self.logger.info(f"Ngrok tunnel created: {public_url}")

            return public_url, httpd, public_tunnel
        except Exception as e:
            self.logger.error(f"Failed to start server or ngrok: {e}")
            return None, None, None

    def _create_media_container_from_url(self, caption: str, video_url: str) -> Optional[str]:
        """Creates a media container using a public video URL."""
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/media"
            params = {
                'media_type': 'REELS',
                'video_url': video_url,
                'caption': caption,
                'access_token': self.access_token
            }
            response = requests.post(url, params=params)
            if response.status_code == 200:
                container_id = response.json().get('id')
                self.logger.info(f"Successfully created media container from URL: {container_id}")
                return container_id
            else:
                self.logger.error(f"Failed to create container from URL: {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception in _create_media_container_from_url: {e}")
            return None

    def post_reel(self, video_path: str, caption: str) -> Dict[str, Any]:
        """Complete workflow to post a reel using the video URL (ngrok) method."""
        self.logger.info(f"Starting reel posting workflow for {video_path} using ngrok.")
        
        public_url, http_server, ngrok_tunnel = self._start_server_and_ngrok(video_path)
        
        if not public_url:
            return {"success": False, "error": "Failed to create public URL with ngrok."}
            
        try:
            container_id = self._create_media_container_from_url(caption, public_url)
            if not container_id:
                return {"success": False, "error": "Container creation from URL failed."}

            self.logger.info("Waiting for video to be processed by Instagram...")
            max_retries = 12
            for i in range(max_retries):
                status_response = self.check_container_status(container_id)
                status_code = status_response.get("status_code")
                
                if status_code == "FINISHED":
                    self.logger.info("Video processing finished successfully.")
                    return self.publish_media(container_id)
                
                if status_code in ["ERROR", "EXPIRED"]:
                    error_msg = f"Container processing failed with status: {status_code}. Full response: {status_response}"
                    self.logger.error(error_msg)
                    return {"success": False, "error": error_msg}

                self.logger.info(f"Polling attempt {i+1}/{max_retries}. Status: {status_code}. Waiting 15s.")
                time.sleep(15)

            return {"success": False, "error": "Video processing timed out."}

        finally:
            if http_server:
                http_server.shutdown()
                http_server.server_close()
                self.logger.info("HTTP server shut down.")
            if ngrok_tunnel:
                ngrok.disconnect(ngrok_tunnel.public_url)
                self.logger.info("Ngrok tunnel closed.")

    def check_container_status(self, container_id: str) -> Dict[str, Any]:
        self.logger.info(f"Checking status for container {container_id}...")
        try:
            url = f"{self.base_url}/{container_id}"
            params = {"fields": "status_code,status", "access_token": self.access_token}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Error checking status: {response.status_code} - {response.text}")
                return {"status_code": "API_ERROR"}
        except Exception as e:
            self.logger.error(f"Exception while checking container status: {e}")
            return {"status_code": "EXCEPTION"}

    def publish_media(self, container_id: str) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/media_publish"
            data = {"creation_id": container_id, "access_token": self.access_token}
            response = requests.post(url, data=data)
            if response.status_code == 200:
                result = response.json()
                media_id = result.get('id')
                self.logger.info(f"Media published successfully: {media_id}")
                return {"success": True, "media_id": media_id}
            else:
                self.logger.error(f"Failed to publish: {response.text}")
                return {"success": False, "error": f"Publish failed: {response.status_code} - {response.text}"}
        except Exception as e:
            self.logger.error(f"Exception in publish_media: {e}")
            return {"success": False, "error": f"Publish error: {str(e)}"}
            
    def get_content_publishing_limit(self) -> Dict[str, Any]:
        """Check API usage limits"""
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/content_publishing_limit"
            params = {
                "fields": "quota_usage,config",
                "access_token": self.access_token
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"Failed to fetch limits: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": f"Limits fetch error: {str(e)}"}

    def get_account_insights(self, period: str = "day", metrics: List[str] = None) -> Dict[str, Any]:
        """Get account insights and analytics"""
        if metrics is None:
            metrics = ["impressions", "reach"]
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/insights"
            params = {"metric": ",".join(metrics), "period": period, "access_token": self.access_token}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"Insights fetch failed: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": f"Insights error: {str(e)}"}

    def get_user_media(self, limit: int = 25) -> Dict[str, Any]:
        """Get user's recent media with insights"""
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/media"
            params = {
                "fields": "id,caption,media_type,media_url,timestamp,like_count,comments_count",
                "limit": limit,
                "access_token": self.access_token
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"Failed to fetch media: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": f"Media fetch error: {str(e)}"}

    def get_media_insights(self, media_id: str) -> Dict[str, Any]:
        """Get insights for a specific media object (Reel)."""
        try:
            metric_list = "reach,likes,comments,saved"
            url = f"{self.base_url}/{media_id}/insights"
            params = {
                "metric": metric_list,
                "access_token": self.access_token
            }
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                error_details = response.json().get("error", {})
                error_message = error_details.get("message", response.text)
                self.logger.error(f"Failed to fetch media insights: {error_message}")
                return {"success": False, "error": error_message}
        except Exception as e:
            return {"success": False, "error": f"Media insights error: {str(e)}"}
