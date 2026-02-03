import unittest
import sys
import os
import json
from unittest.mock import patch, mock_open

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from main import clean_video_name, get_videos

class TestVideoLogic(unittest.TestCase):
    def setUp(self):
        """Define reusable fake file system data"""
        self.local_root = 'static/temp'
        self.folder_name = "2026-01-21T09_56_05.967648-14c53e20-b364-46b0-ae40-9fb486f47a11-video.mp4"
        self.original_video = self.folder_name
        self.translated_video = f"{self.folder_name}.en-GB.mp4"
            
        self.files_list = [
            self.original_video,      
            self.translated_video,
            "metadata.json",
            "audio_0.wav"
        ]
            
        self.fake_meta = json.dumps({
            "original_language": "en-GB",
            "translate_language": "it-IT", 
            "duration": 10.5,
            "speakers": [
                {"speaker_id": "speaker_1", "voice": "voice_1"},
                {"speaker_id": "speaker_1", "voice": "voice_1"}
            ]
        })

    @patch('main.os.walk') 
    @patch('main.os.path.exists')
    @patch('main.os.path.getmtime')
    @patch('main.open', new_callable=mock_open)
    @patch('main.mount_point', 'static/temp')
    def test_get_videos_local_mode(self, mock_file, mock_getmtime, mock_exists, mock_walk):
        full_path = f"{self.local_root}/{self.folder_name}"
        mock_walk.return_value = [(full_path, [], self.files_list)]
        mock_exists.return_value = True
        mock_getmtime.return_value = 1700000000.0
        mock_file.return_value.read.return_value = self.fake_meta

        results = get_videos()
        
        # Verify filtering: should only find 1 (the translated video), skipping the original
        self.assertEqual(len(results), 1)
        video = results[0]

        # In main.py, local web_path uses /temp/ prefix
        expected_url = f"/temp/{self.folder_name}/{self.translated_video}"
        self.assertEqual(video['url'], expected_url)
        
        # Verify metadata extraction and speaker deduplication
        self.assertEqual(video['original_language'], "en-GB")
        self.assertEqual(len(video['speakers']), 1) # Deduplicated
        self.assertEqual(video['speakers'][0]['voice'], "voice_1")

    def test_clean_video_name(self):
        """Testing clean_video_name function"""
        raw_name = "2026-01-16T13_31_34.830635-ed69b287-ac8d-4876-a8c3-481208407350-video.mp4"
        self.assertEqual(clean_video_name(raw_name), "video.mp4")
        
        raw_name = "2026-01-16T13_31_34.830635-ed69b287-ac8d-4876-a8c3-481208407350-video.mp4.en-GB.mp4"
        self.assertEqual(clean_video_name(raw_name), "video.mp4.en-GB.mp4")

if __name__ == '__main__':
    unittest.main()