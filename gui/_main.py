"""Generates product video using Veo3 and stores its status in Firestore."""

import sys, traceback
import datetime
import logging
import os
import json
import functions_framework
from random import randrange
from typing import Dict, Any
from dubble.dubble import DubbingError
from dubble.dubble import DubbleTTSData
from dubble.gen_ai import GenAIInvoker
from dubble.gen_ai import VoiceSelector
from dubble.gen_ai import DubbleLLM
from google.cloud import storage
from dubble.configuration import DubbleConfig
from google.api_core.exceptions import NotFound
from google.cloud import firestore
from google.cloud import logging as cloud_logging
from google.cloud import storage
from dubble.av import separate_audio_from_video
from dubble.av import assemble_final_video


from moviepy.editor import AudioFileClip
from moviepy.editor import CompositeAudioClip
from moviepy.editor import VideoFileClip
from moviepy.editor import concatenate_audioclips



def __video_test(audio, background, video):
    clips = []

    clip = AudioFileClip(audio)
    
    clip.start=7.00    
    
    clip.end = clip.start + clip.duration
    print(clip.start)
    clips.append(clip)
    

    #starts = []
    #for clip in clips:
    #    starts.append(clip.start)
    #
    #clips = [clip.set_start(starts[index]) for index, clip in enumerate(clips)]
    #print(clips)
    background_clip = AudioFileClip(background)
    #voice_clips = concatenate_audioclips(clips)
    final_audio = CompositeAudioClip(
        [background_clip.volumex(0.3)] + clips
    )

    #final_audio_clips = [background_clip.volumex(0.3)]
    #if voice_clips:
    #    final_audio_clips.append(voice_clips)

    #final_audio = CompositeAudioClip(final_audio_clips)

    original_video_clip = VideoFileClip(video)

    final_audio.duration = min(
        final_audio.duration, original_video_clip.duration
    )
    print(f"final_audio_duartion {final_audio.duration}")
    final_video = original_video_clip.set_audio(final_audio)


    output_filename = f"video_dubbed.mp4"
    print(f"output_filename {output_filename}")

    final_video.write_videofile(
        output_filename, codec='libx264', audio_codec='aac'
    )

__video_test(
    audio="outputs/feb3fa90-cc9b-4fc7-be79-77127a0ec10f/generated_SPEAKER_01_0_05.wav",
    background="outputs/feb3fa90-cc9b-4fc7-be79-77127a0ec10f/htdemucs/original_audio/no_vocals.wav",
    video="uploads/f29e5990-faa5-40b5-a554-9ca9dee5e438_macd_it.mp4"
)
#try:
#    file_name = "_main.py"
#    json_object = None
#    with open("payload.txt", 'r', encoding='utf-8') as file:
#        # Read the file content as a single string
#        data_string = file.read()
#
#        # Use json.loads() to parse the string into a Python object
#        json_object = json.loads(data_string)
#
#    print(json_object)
#
#    update_sheets_row(json_object, file_name)
#except Exception as e:
#    traceback