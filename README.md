# gTech Ads Ariel for AI Video Ad Dubbing

### Ariel is an open-source Python library that facilitates efficient and cost-effective dubbing of video ads into multiple languages.

##### _This is not an official Google product._

[Overview](#overview) •
[Features](#features) •
[Benefits](#benefits) •
[Building Blocks](#building-blocks) •
[Getting Started](#getting-started) •
[References](#references)

## Overview

Ariel is a cutting-edge solution designed to enhance the global reach of digital advertising. It enables advertisers to automate the translation and dubbing of their video ads into a wide range of languages.

## Features

*   **Automated Dubbing:** Streamline the generation of high-quality dubbed versions of video ads in various target languages.
*   **Scalability:** Handle large volumes of videos and diverse languages efficiently.
*   **User-Friendly:** Offers a straightforward API and/or user interface for simplified operation.
*   **Cost-Effective:** Significantly reduce dubbing costs compared to traditional methods. The primary expenses are limited to Gemini API and Text-To-Speech API calls.

## Benefits

*   **Enhanced Ad Performance:** Improve viewer engagement and potentially increase conversion rates with localized ads.
*   **Streamlined Production:** Minimize the time and cost associated with manual translation and voiceover work.
*   **Rapid Turnaround:** Quickly generate dubbed versions of ads to accelerate multilingual campaign deployment.
*   **Expanded Global Reach:** Reach broader audiences worldwide with localized advertising content.

## Building Blocks

Ariel leverages a powerful combination of state-of-the-art AI and audio processing techniques to deliver accurate and efficient dubbing results:

1.  **Video Processing:** Extracts the audio track from the input video file.
2.  **Audio Processing:**
    *   **DEMUCS:** Employed for advanced audio source separation.
    *   **pyannote:** Performs speaker diarization to identify and separate individual speakers.
3.  **Speech-To-Text (STT):**
    *   **faster-whisper:** A high-performance speech-to-text model.
    *   **Gemini 1.5 Flash:** A powerful multimodal language model that contributes to enhanced transcription.
4.  **Translation:**
    *   **Gemini 1.5 Flash:** Leverages its language understanding for accurate and contextually relevant translation.
5.  **Text-to-Speech (TTS):**
    *   **GCP's Text-To-Speech:** Generates natural-sounding speech in the target language.

## Getting Started

1.  **System Requirements:**
    *   Ariel is designed to run on systems with FFmpeg installed. If you don't have it, run the following commands in your terminal:

    ```bash
    sudo apt update
    sudo apt install ffmpeg
    ```

2.  **Installation:**

    ```bash
    pip install ariel
    ```

3.  **Usage:**

    ```bash
    python main.py --input_file=<path_to_video> --output_directory=<output_dir> --advertiser_name=<name> --original_language=<lang_code> --target_language=<lang_code> [--number_of_speakers=<num>] [--diarization_instructions=<instructions>] [--translation_instructions=<instructions>] [--merge_utterances=<True/False>] [--minimum_merge_threshold=<seconds>] [--preferred_voices=<voice1>,<voice2>] [--clean_up=<True/False>] [--pyannote_model=<model_name>] [--diarization_system_instructions=<instructions>] [--translation_system_instructions=<instructions>] [--hugging_face_token=<token>] [--gemini_token=<token>] [--model_name=<model_name>] [--temperature=<value>] [--top_p=<value>] [--top_k=<value>] [--max_output_tokens=<value>] [--response_mime_type=<value>]
    ```

4.  **Configuration:** (Optional)
    *   Customize settings for speaker diarization, translation, voice selection, and more using the command-line flags.

## References

*   **DEMUCS:** https://github.com/facebookresearch/demucs
*   **pyannote:** https://github.com/pyannote/pyannote-audio
*   **faster-whisper:** https://github.com/SYSTRAN/faster-whisper
