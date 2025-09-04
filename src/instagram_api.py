# -*- coding: utf-8 -*-
"""
Instagram Graph API integration for ReelPilot AI.

This module provides the InstagramAPI class, which encapsulates all interactions
with the Facebook Graph API for Instagram. It handles posting reels, fetching
account data, retrieving media insights, and performing AI-powered analysis
of other business accounts using Google's Gemini model.
"""

import requests
import json
import time
import os
from typing import Dict, Any, Optional, List, Tuple
import logging
from pathlib import Path
from datetime import datetime, timedelta
import hmac
import hashlib
import google.generativeai as genai
import threading
import http.server
import socketserver
from pyngrok import ngrok, conf
import atexit

class InstagramAPI:
    """
    Manages all interactions with the Instagram Graph API and AI analysis.

    This class provides a high-level interface for complex operations like
    posting reels via a persistent ngrok tunnel, fetching analytics, and generating
    in-depth account summaries with generative AI.
    """

    def __init__(self, config):
        """
        Initializes the InstagramAPI client.

        Args:
            config: A Config object with application settings and credentials.
        """
        self.config = config
        self.access_token = config.access_token
        self.app_id = config.app_id
        self.app_secret = config.app_secret
        self.instagram_account_id = config.instagram_account_id
        self.base_url = "https://graph.facebook.com/v20.0"
        
        self.logger = logging.getLogger(__name__)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

        # Attributes for the persistent tunnel
        self.http_server = None
        self.ngrok_tunnel = None
        self.public_url_base = None

        if config.ngrok_authtoken:
            conf.get_default().auth_token = config.ngrok_authtoken
        
        if self.config.google_api_key:
            try:
                genai.configure(api_key=self.config.google_api_key)
            except Exception as e:
                self.logger.error(f"Failed to configure Google AI: {e}")
        
        # Register a cleanup function to be called on application exit
        atexit.register(self.stop_server_and_ngrok)

    def start_server_and_ngrok(self) -> bool:
        """
        Starts a single, persistent web server and ngrok tunnel for the app's lifetime.
        
        Returns:
            bool: True if successful, False otherwise.
        """
        if self.ngrok_tunnel:
            self.logger.info("Server and ngrok tunnel are already running.")
            return True
        try:
            port = 8000
            # Serve from the main video storage directory, ensuring it exists.
            video_directory = self.config.video_storage_path
            os.makedirs(video_directory, exist_ok=True)

            class DirectoryHandler(http.server.SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=video_directory, **kwargs)

            # Allow the port to be reused immediately after shutdown
            socketserver.TCPServer.allow_reuse_address = True
            self.http_server = socketserver.TCPServer(("", port), DirectoryHandler)
            
            server_thread = threading.Thread(target=self.http_server.serve_forever)
            server_thread.daemon = True
            server_thread.start()
            self.logger.info(f"Persistent HTTP server started on port {port}")

            self.ngrok_tunnel = ngrok.connect(port, "http")
            self.public_url_base = self.ngrok_tunnel.public_url
            self.logger.info(f"Persistent Ngrok tunnel created: {self.public_url_base}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start persistent server or ngrok: {e}")
            if self.http_server:
                self.http_server.shutdown()
            return False

    def stop_server_and_ngrok(self):
        """Stops the web server and disconnects the ngrok tunnel."""
        if self.http_server:
            self.http_server.shutdown()
            self.http_server.server_close()
            self.logger.info("Persistent HTTP server shut down.")
        if self.ngrok_tunnel:
            ngrok.disconnect(self.ngrok_tunnel.public_url)
            self.logger.info("Persistent Ngrok tunnel closed.")

    def _create_media_container_from_url(self, caption: str, video_url: str) -> Optional[str]:
        """Creates an Instagram media container using a public video URL."""
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/media"
            params = {
                'media_type': 'REELS', 'video_url': video_url,
                'caption': caption, 'access_token': self.access_token
            }
            response = requests.post(url, params=params)
            if response.status_code == 200:
                container_id = response.json().get('id')
                self.logger.info(f"Successfully created media container: {container_id}")
                return container_id
            else:
                self.logger.error(f"Failed to create container from URL: {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception in _create_media_container_from_url: {e}")
            return None

    def post_reel(self, video_path: str, caption: str) -> Dict[str, Any]:
        """
        Posts a reel by reusing the persistent ngrok tunnel.
        """
        self.logger.info(f"Starting reel posting workflow for {video_path}")
        
        if not self.public_url_base:
            return {"success": False, "error": "Ngrok tunnel is not running. Please restart the application."}
        
        video_filename = os.path.basename(video_path)
        public_video_url = f"{self.public_url_base}/{video_filename}"
        self.logger.info(f"Using public video URL: {public_video_url}")

        container_id = self._create_media_container_from_url(caption, public_video_url)
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
                error_msg = f"Container processing failed with status: {status_code}."
                self.logger.error(error_msg)
                return {"success": False, "error": error_msg}

            self.logger.info(f"Polling attempt {i+1}/{max_retries}. Status: {status_code}. Waiting 15s.")
            time.sleep(15)

        return {"success": False, "error": "Video processing timed out."}

    def check_container_status(self, container_id: str) -> Dict[str, Any]:
        self.logger.info(f"Checking status for container {container_id}...")
        try:
            url = f"{self.base_url}/{container_id}"
            params = {"fields": "status_code,status", "access_token": self.access_token}
            response = requests.get(url, params=params)
            return response.json() if response.status_code == 200 else {"status_code": "API_ERROR"}
        except Exception as e:
            self.logger.error(f"Exception checking container status: {e}")
            return {"status_code": "EXCEPTION"}

    def publish_media(self, container_id: str) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/media_publish"
            data = {"creation_id": container_id, "access_token": self.access_token}
            response = requests.post(url, data=data)
            if response.status_code == 200:
                media_id = response.json().get('id')
                self.logger.info(f"Media published successfully: {media_id}")
                return {"success": True, "media_id": media_id}
            else:
                self.logger.error(f"Failed to publish: {response.text}")
                return {"success": False, "error": f"Publish failed: {response.text}"}
        except Exception as e:
            self.logger.error(f"Exception in publish_media: {e}")
            return {"success": False, "error": str(e)}

    def get_content_publishing_limit(self) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/content_publishing_limit"
            params = {"fields": "quota_usage,config", "access_token": self.access_token}
            response = requests.get(url, params=params)
            return {"success": True, "data": response.json()} if response.status_code == 200 else {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_account_insights(self, period: str = "day", metrics: List[str] = None) -> Dict[str, Any]:
        if metrics is None:
            metrics = ["impressions", "reach"]
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/insights"
            params = {"metric": ",".join(metrics), "period": period, "access_token": self.access_token}
            response = requests.get(url, params=params)
            return {"success": True, "data": response.json()} if response.status_code == 200 else {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}
            
    def _generate_ai_summary(self, username: str, profile_data: Dict[str, Any]) -> str:
        if not self.config.google_api_key:
            return "**AI Analysis Skipped:** A Google AI API Key has not been configured."
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            if 'media' in profile_data and 'data' in profile_data['media']:
                for post in profile_data['media']['data']:
                    post.pop('media_url', None)
                    if 'caption' in post and post['caption']:
                        post['caption'] = post['caption'][:150] + '...'
            prompt = f"""
            You are a seasoned social media strategist. Analyze the Instagram account @{username} based on the following JSON data, which includes follower counts and metrics from their last 10 posts.
            Data:
            ```json
            {json.dumps(profile_data, indent=2)}
            ```
            Structure your response in Markdown with these sections:
            ### In-Depth Analysis
            Provide a professional summary. Interpret the engagement rate (likes + comments / followers). Is it high or low for an account this size? Discuss their follower-to-post ratio.
            ### Content & Posting Cadence
            Analyze content from captions and engagement. What content performs best? Analyze `timestamp` data to identify their posting consistency.
            ### Actionable Growth Plan
            Provide a bulleted list of at least three specific, creative, and actionable growth strategies inspired by your analysis. Avoid generic advice.
            """
            response = model.generate_content(prompt)
            return response.text
        except Exception as e:
            self.logger.error(f"Error generating AI summary: {e}")
            error_message = str(e)
            if "API_KEY_INVALID" in error_message or "PermissionDenied" in error_message:
                return "**AI Analysis Failed:** Your Google AI API Key is invalid or lacks permissions."
            elif "Billing" in error_message:
                 return "**AI Analysis Failed:** There is an issue with the billing account for your Google Cloud project."
            else:
                return f"**AI Analysis Failed:** An unexpected error occurred: {error_message}"

    def test_connection(self) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/{self.instagram_account_id}"
            params = {"fields": "id,username,media_count,followers_count", "access_token": self.access_token}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": f"Connection error: {str(e)}"}

    def get_business_user_analysis(self, username: str) -> Dict[str, Any]:
        self.logger.info(f"Executing real-time analysis for username: {username}")
        if not all([self.instagram_account_id, self.access_token, self.app_secret]):
            return {"success": False, "error": "App is not fully configured."}
        if not username:
            return {"success": False, "error": "Username cannot be empty."}
        user_fields = "business_discovery.username({username}){{followers_count,media_count,media.limit(10){{caption,like_count,comments_count,timestamp,media_url}}}}"
        try:
            app_secret_proof = hmac.new(
                self.app_secret.encode('utf-8'),
                msg=self.access_token.encode('utf-8'),
                digestmod=hashlib.sha256
            ).hexdigest()
            url = f"{self.base_url}/{self.instagram_account_id}"
            params = {
                "fields": user_fields.format(username=username),
                "access_token": self.access_token,
                "appsecret_proof": app_secret_proof
            }
            response = requests.get(url, params=params)
            if response.status_code != 200:
                error_data = response.json().get('error', {})
                return {"success": False, "error": error_data.get('message', 'An unknown API error occurred.')}
            data = response.json()
            if 'business_discovery' not in data:
                return {"success": False, "error": f"Could not find Business account '{username}'. It may be a personal account."}
            discovery_data = data['business_discovery']
            followers = discovery_data.get('followers_count', 0)
            media_list = discovery_data.get('media', {}).get('data', [])
            ai_summary = self._generate_ai_summary(username, discovery_data)
            avg_likes, avg_comments, engagement_rate = 0, 0, 0
            if media_list and followers > 0:
                total_likes = sum(p.get('like_count', 0) for p in media_list)
                total_comments = sum(p.get('comments_count', 0) for p in media_list)
                avg_interactions = (total_likes + total_comments) / len(media_list)
                engagement_rate = (avg_interactions / followers) * 100
            return {
                "success": True,
                "data": {
                    "username": username, "followers_count": followers,
                    "media_count": discovery_data.get('media_count'),
                    "metrics": {"engagement_rate_percent": engagement_rate},
                    "ai_summary": ai_summary
                }
            }
        except Exception as e:
            self.logger.error(f"An exception occurred during analysis: {e}")
            return {"success": False, "error": str(e)}

    def get_user_media(self, limit: int = 25) -> Dict[str, Any]:
        try:
            url = f"{self.base_url}/{self.instagram_account_id}/media"
            params = {
                "fields": "id,caption,media_type,media_url,timestamp,like_count,comments_count",
                "limit": limit, "access_token": self.access_token
            }
            response = requests.get(url, params=params)
            return {"success": True, "data": response.json()} if response.status_code == 200 else {"success": False, "error": response.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_all_user_media(self, username: str) -> Dict[str, Any]:
        """
        Fetches all recent media for a given user, handling pagination and carousels.
        """
        self.logger.info(f"Fetching all media for user: {username}")
        # --- MODIFIED: Added 'children' field to fetch carousel items ---
        user_fields = "business_discovery.username({username}){{media{{caption,media_type,media_url,thumbnail_url,timestamp,permalink,children{{media_url,media_type,id}}}}}}"
        
        try:
            url = f"{self.base_url}/{self.instagram_account_id}"
            params = {"fields": user_fields.format(username=username), "access_token": self.access_token}
            all_media = []
            
            while url:
                response = requests.get(url, params=params)
                params = {} # Params are only needed for the first request
                
                if response.status_code != 200:
                    error_data = response.json().get('error', {})
                    return {"success": False, "error": error_data.get('message', 'An API error occurred.')}

                data = response.json()
                if 'business_discovery' not in data:
                    return {"success": False, "error": f"Could not find Business account '{username}'."}
                
                discovery_data = data.get('business_discovery', {}).get('media', {})
                
                if 'data' in discovery_data:
                    all_media.extend(discovery_data['data'])

                url = discovery_data.get('paging', {}).get('next')

            return {"success": True, "data": all_media}
        except Exception as e:
            self.logger.error(f"An exception occurred during media fetch: {e}")
            return {"success": False, "error": str(e)}

    def get_media_insights(self, media_id: str) -> Dict[str, Any]:
        try:
            metric_list = "reach,likes,comments,saved"
            url = f"{self.base_url}/{media_id}/insights"
            params = {"metric": metric_list, "access_token": self.access_token}
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                error_message = response.json().get("error", {}).get("message", response.text)
                self.logger.error(f"Failed to fetch media insights: {error_message}")
                return {"success": False, "error": error_message}
        except Exception as e:
            return {"success": False, "error": str(e)}
