"""Tests for library page logic: cleaning video name, and getting the list of the translated videos that needs to be shown on Library page"""

# Copyright 2026 Google LLC

# Licensed under the Apache License, Version 2.0 (the "License"); you may not
# use this file except in compliance with the License. You may obtain a copy
# of the License at

#   http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import unittest
import sys
import os
import json
from unittest.mock import patch, mock_open

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import clean_video_name, get_videos

class TestVideoLogic(unittest.TestCase):
  def setUp(self):
    """define reusable fake file system data"""
    self.local_root = 'static/temp'
    self.cloud_root = '/mnt/ariel'
    self.folder_name = "2026-01-21T09_56_05.967648-14c53e20-b364-46b0-ae40-9fb486f47a11-video.mp4"
    self.original_video = "2026-01-21T09_56_05.967648-14c53e20-b364-46b0-ae40-9fb486f47a11-video.mp4"
    self.translated_video = "2026-01-21T09_56_05.967648-14c53e20-b364-46b0-ae40-9fb486f47a11-video.mp4.en-GB.mp4"
        
    self.files_list = [
      self.original_video,      
      self.translated_video,
      "metadata.json",
      "audio_0.wav"
    ]
        
    self.fake_meta = json.dumps({
      "original_language": "en-GB",
      "translate_language": "it-IT", 
      "speakers": [{
        "speaker_id": "speaker_1",
        "voice": "voice_1"
        }, {
        "speaker_id": "speaker_2",
        "voice": "voice_2"
        }]
      })

  # testing getting translated videos in local mode
  @patch('main.os.walk') 
  @patch('main.os.path.exists')
  @patch('main.os.path.getmtime')
  @patch('main.open', new_callable=mock_open)
  @patch('main.mount_point', 'static/temp') 
  @patch('main.url_prefix', '/mnt')
  def test_get_videos_local_mode(self, mock_file, mock_getmtime, mock_exists, mock_walk):
      
      full_path = f"{self.local_root}/{self.folder_name}"
      mock_walk.return_value = [(full_path, [], self.files_list)]
      mock_exists.return_value = True
      mock_getmtime.return_value = 1700000000.0
      mock_file.return_value.read.return_value = self.fake_meta

      results = get_videos()
      self.assertEqual(len(results), 1)
      video = results[0]

      expected_url = f"/mnt/{self.folder_name}/{self.translated_video}"
      self.assertEqual(video['url'], expected_url)

  # testing getting translated videos in cloud mode
  @patch('main.os.walk')
  @patch('main.os.path.exists')
  @patch('main.os.path.getmtime')
  @patch('main.open', new_callable=mock_open)
  @patch('main.mount_point', '/mnt/ariel')
  @patch('main.url_prefix', '/mnt/ariel')
  def test_get_videos_cloud_mode(self, mock_file, mock_getmtime, mock_exists, mock_walk):
      full_path = f"{self.cloud_root}/{self.folder_name}"
      mock_walk.return_value = [(full_path, [], self.files_list)]
      mock_exists.return_value = True
      mock_getmtime.return_value = 1700000000.0
      mock_file.return_value.read.return_value = self.fake_meta

      results = get_videos()
      self.assertEqual(len(results), 1)
      video = results[0]

      expected_url = f"/mnt/ariel/{self.folder_name}/{self.translated_video}"
      self.assertEqual(video['url'], expected_url)

  def test_clean_video_name(self):
      """testing clean_video_name function"""
      # testing video name with uuid prefix
      raw_name = "2026-01-16T13_31_34.830635-ed69b287-ac8d-4876-a8c3-481208407350-video.mp4"
      self.assertEqual(clean_video_name(raw_name), "video.mp4")
      
      # testing translated video name with uuid prefix and language code
      raw_name = "2026-01-16T13_31_34.830635-ed69b287-ac8d-4876-a8c3-481208407350-video.mp4.en-GB.mp4"
      self.assertEqual(clean_video_name(raw_name), "video.mp4.en-GB.mp4")

if __name__ == '__main__':
  unittest.main()