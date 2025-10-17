# dubble_logic.py

import os
import logging
import time

import json
from typing import Any
from dubble.gen_ai import GenAIInvoker
from dubble.configuration import DubbleConfig
from dubble.av import separate_audio_from_video
from dubble.av import assemble_final_video as assemble_video
from dubble.gen_ai import DubbleLLM
from dubble.gen_ai import VoiceSelector
from moviepy.editor import AudioFileClip
from dubble.dubble import DubbleTTSData
from dubble.dubble import DubbingError
from google.cloud import storage
import uuid

logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)


def download_from_gcs(gcs_url: str, destination_directory: str) -> str:
    """Downloads a file from a GCS URL to a local directory."""
    try:
        storage_client = storage.Client()
        bucket_name, blob_name = gcs_url.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        # Create a unique filename to avoid collisions
        unique_filename = f"{uuid.uuid4()}_{blob_name.split('/')[-1]}"
        destination_path = os.path.join(destination_directory, unique_filename)

        blob.download_to_filename(destination_path)
        logger.info(f"Downloaded {gcs_url} to {destination_path}")
        return destination_path
    except Exception as e:
        logger.error(f"Failed to download from GCS URL {gcs_url}. Reason: {e}")
        raise




def upload_to_gcs(local_file_path: str, gcs_url: str) -> str:
    """Uploads a local file to a GCS URL."""
    try:
        storage_client = storage.Client()
        bucket_name, blob_name = gcs_url.replace("gs://", "").split("/", 1)
        
        # Modify the blob name to indicate it's a dubbed version
        blob_name_parts = blob_name.split('.')
        blob_name_parts.insert(-1, "dubbed")
        dubbed_blob_name = ".".join(blob_name_parts)

        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(dubbed_blob_name)

        blob.upload_from_filename(local_file_path)
        dubbed_gcs_url = f"gs://{bucket_name}/{dubbed_blob_name}"
        logger.info(f"Uploaded {local_file_path} to {dubbed_gcs_url}")
        return dubbed_gcs_url
    except Exception as e:
        logger.error(f"Failed to upload to GCS URL {gcs_url}. Reason: {e}")
        raise

def initialize(config_params: dict) -> DubbleConfig:
    
    config_params.pop("prompt_library")
    config = DubbleConfig(**config_params)
    
    GenAIInvoker.genai_client = None
    logger.info("Calling separate audio from video...")
    config = separate_audio_from_video(config)
    logger.info("Completed separate audio from video...")
    
    return config.to_json()


def diarize(config: DubbleConfig):
    """
    Initializes the configuration and performs the initial analysis (diarization).
    """
 
    if not config.script:
        llm = DubbleLLM(config)
        dubbing_data = llm.diarization(config)
        print(dubbing_data)
        dubbing_data = llm.translate_utterances(dubbing_data, config)
        voice_selector = VoiceSelector(config)
        dubbing_data = voice_selector.find_best_voices(dubbing_data, config)
    else:
       try:
        logging.info("Using script provided by user for TTS")
        config.script = json.loads(config.script)
        
        dubbing_data = []
        for item in config.script:
            dubbing_data.append(DubbleTTSData.from_dict(item, config))
       except Exception as e:
           raise DubbingError("Check your Manual TTS script")

    utterances = [vars(u) for u in dubbing_data]
    
    return utterances


def create_default_utterances(config: DubbleConfig) -> list[dict[str, Any]]:

    config.script = {
        "speaker_id": "SPEAKER_01",
        "start": 0.05,
        "end": 3.48,
        "original_text": "Es el texto original",
        "translated_text": "It's the original text",
        "tts_prompt": config.prompt_library["tts_prompt_template"],
        "special_instructions": "",
        "voice_name": "Zephyr",
        "sync_mode": "Natural Duration",
        "gender": "Male",
        "age": "Young Adult",
        "pitch": "Lower-middle",
        "tone": "Upbeat",
        "vocal_style_prompt": "A friendly and energetic young adult male voice, speaking with a fast-paced, upbeat delivery. The tone is enthusiastic and persuasive, perfect for an advertisement targeting a youthful audience, making the service sound exciting and convenient.",
        "suggested_voice": ""
    }
    
    utterance = DubbleTTSData.from_dict(config.script, config)
    utterances = [json.loads(utterance.to_json())]
    
    return utterances

def translate_utterance(utterance_data: dict, config: DubbleConfig) -> str:

    llm = DubbleLLM(config)
    utterance = DubbleTTSData.from_dict(utterance_data, config)
    utterance = llm.translate_utterance(utterance, config)
    
    return utterance.translated_text


def generate_single_utterance_speech(utterance_data: dict, config: DubbleConfig, job_dir: str):
    """
    Generates speech for a single utterance.
    """

    llm = DubbleLLM(config)

    
    # Convert utterance dict back to DubbleTTSData object
    utterance = DubbleTTSData.from_dict(utterance_data, config)
    
    generation_id = f"{utterance.speaker_id}_{utterance.start:.2f}".replace('.', '_')

    audio_clip, utterance = llm.generate_timed_speech_for_utterance(
        generation_id=generation_id,
        utterance=utterance,
        config=config
    )

    # The function returns a moviepy clip object, we need to save it to a file
    # and return the path.
    if audio_clip:
        output_filename =  f"generated_{generation_id}_{int(time.time() * 1000)}.wav"
        output_path = os.path.join(job_dir, output_filename)
        audio_clip.write_audiofile(output_path)
        return output_path, utterance.translated_text
    
    return None


def assemble_final_video(utterances: list, config: DubbleConfig):
    """
    Assembles the final video with the new audio track using updated timings.
    """
    from urllib.parse import urlparse
    print(utterances)
    timed_vocal_clips = []
    
    for utterance in utterances:
        audio_url = utterance.get("audio_url")
        start_time = utterance.get("start")
        end_time = utterance.get("end")
        

        if not audio_url or start_time is None:
            logger.warning(f"Skipping utterance due to missing audio_url or start time: {utterance}")
            continue

        # The frontend sends the full audio URL. We need to convert it to a local file path.
        # The path in the URL (e.g., /outputs/...) is relative to the web server root (`gui` dir).
        relative_path = urlparse(audio_url).path.lstrip('/')
        full_audio_path = os.path.abspath(relative_path)

        if os.path.exists(full_audio_path):
            logger.debug(f"Adding audio clip: {full_audio_path} at {start_time}s")
            clip = AudioFileClip(full_audio_path)
            clip.start = start_time # Set the start time of the clip
            clip.end = end_time
            timed_vocal_clips.append(clip)
        else:
            logger.warning(f"Audio file not found for utterance: {utterance}. Path checked: {full_audio_path}")
    logger.debug(f"Times vocal clips {timed_vocal_clips}")
    final_video_path = assemble_video(
        config=config,
        timed_vocal_clips=timed_vocal_clips
    )

    return final_video_path