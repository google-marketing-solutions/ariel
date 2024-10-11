# gTech Ads Ariel for AI Video Ad Dubbing

### Ariel is an open-source Python library that facilitates efficient and cost-effective dubbing of video ads into multiple languages.

[![python](https://img.shields.io/badge/Python->=3.10-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org)
[![PyPI](https://img.shields.io/pypi/v/gtech-ariel?logo=pypi&logoColor=white&style=flat)](https://pypi.org/project/gtech-ariel/)
[![GitHub last commit](https://img.shields.io/github/last-commit/google-marketing-solutions/ariel)](https://github.com/google-marketing-solutions/ariel/commits)
[![Code Style: Google](https://img.shields.io/badge/code%20style-google-blueviolet.svg)](https://google.github.io/styleguide/pyguide.html)
[![Open in Colab](https://img.shields.io/badge/Dubbing_Workflow-blue?style=flat&logo=google%20colab&labelColor=grey)](https://colab.research.google.com/github/google-marketing-solutions/ariel/blob/main/examples/dubbing_workflow.ipynb)

##### _This is not an official Google product._

[Overview](#overview) •
[Features](#features) •
[Benefits](#benefits) •
[Building Blocks](#building-blocks) •
[Requirements](#requirements) •
[Language Compatibility](#language-compatibility) •
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
    *   **[OPTIONAL] ElevenLabs:** An alternative API to generate speech. It's recommened for the best results. **WARNING:** ElevenLabs is a paid solution and will generate extra costs. See the pricing [here](https://elevenlabs.io/pricing).

## Requirements

*   **System Requirements:**
    *   **FFmpeg:** For video and audio processing. If not installed, you can use the following commands:
        ```bash
        sudo apt update
        sudo apt install ffmpeg
        ```
    *   **GPU (Recommended):** For optimal performance, especially with larger videos.
*   **Accounts and Tokens:**
    *   **Google Cloud Platform (GCP) Project:** Set up a GCP project. See [here](https://cloud.google.com/resource-manager/docs/creating-managing-projects) for instructions.
    *   **Enabled Text-To-Speech API:** Enable the Text-To-Speech API in your GCP project. See [here](https://cloud.google.com/text-to-speech/docs/before-you-begin) for instructions.
    *   **Hugging Face Token:** To access the PyAnnote speaker diarization model. See [here](https://huggingface.co/docs/hub/en/security-tokens) on how to get the token.
    *   **Google AI Studio Token:** To access the Gemini language model. See [here](https://ai.google.dev/gemini-api/docs) on how to get the token.
    *   **[OPTIONAL] ElevenLabs API:** To access the ElevenLabs API. See [here](https://help.elevenlabs.io/hc/en-us/articles/14599447207697-How-to-authorize-yourself-using-your-xi-api-key).
*   **User Agreements:**
    *   **Hugging Face Model License:** You must accept the user conditions for the PyAnnote speaker diarization [here](https://huggingface.co/pyannote/speaker-diarization-3.1) and segmentation models [here](https://huggingface.co/pyannote/segmentation-3.0).

## Language Compatibility

You can dub video ads from and to the following languages:

*   Arabic (ar-SA), (ar-EG)
*   Bengali (bn-BD), (bn-IN)
*   Bulgarian (bg-BG)
*   Chinese (Simplified) (zh-CN)
*   Chinese (Traditional) (zh-TW)
*   Croatian (hr-HR)
*   Czech (cs-CZ)
*   Danish (da-DK)
*   Dutch (nl-NL)
*   English (en-US), (en-GB), (en-CA), (en-AU)
*   Estonian (et-EE)
*   Finnish (fi-FI)
*   French (fr-FR), (fr-CA)
*   German (de-DE)
*   Greek (el-GR)
*   Gujarati (gu-IN)
*   Hebrew (he-IL) (Note: Not supported with ElevenLabs API)
*   Hindi (hi-IN)
*   Hungarian (hu-HU)
*   Indonesian (id-ID)
*   Italian (it-IT)
*   Japanese (ja-JP)
*   Kannada (kn-IN)
*   Korean (ko-KR)
*   Latvian (lv-LV)
*   Lithuanian (lt-LT)
*   Malayalam (ml-IN)
*   Marathi (mr-IN)
*   Norwegian (nb-NO), (nn-NO)
*   Polish (pl-PL)
*   Portuguese (pt-PT), (pt-BR)
*   Romanian (ro-RO)
*   Russian (ru-RU)
*   Serbian (sr-RS)
*   Slovak (sk-SK)
*   Slovenian (sl-SI)
*   Spanish (es-ES), (es-MX)
*   Swahili (sw-KE)
*   Swedish (sv-SE)
*   Tamil (ta-IN), (ta-LK)
*   Telugu (te-IN)
*   Thai (th-TH)
*   Turkish (tr-TR)
*   Ukrainian (uk-UA)
*   Vietnamese (vi-VN)

The language coverage depends on the underlying services. Check the below for any changes:

### Speech-to-Text (Whisper)

Ariel leverages the open-source Whisper model, which supports a wide array of languages for speech-to-text conversion. The supported languages can be found [here](https://github.com/openai/whisper).


### Translation (Gemini)

Gemini, the language model used for translation, is proficient in multiple languages. For the most current list of supported languages, refer to [here](https://cloud.google.com/gemini/docs/codeassist/supported-languages).

### Text-to-Speech (GCP Text-to-Speech or ElevenLabs)

GCP Text-to-Speech offers an extensive selection of voices in various languages. For a comprehensive list of supported languages and available voices, refer to [here](https://cloud.google.com/text-to-speech/docs/voices).
ElevenLabs API is an alterantive to GCP Text-to-Speech. See a list of supported languages [here](https://elevenlabs.io/docs/api-reference/text-to-speech#supported-languages).


## Getting Started

1.  **Installation:**

    ```bash
    pip install gtech-ariel
    ```

2.  **Usage:**

    ```bash
    python main.py --input_file=<path_to_video> --output_directory=<output_dir> --advertiser_name=<name> --original_language=<lang_code> --target_language=<lang_code> [--number_of_speakers=<num>] [--diarization_instructions=<instructions>] [--translation_instructions=<instructions>] [--merge_utterances=<True/False>] [--minimum_merge_threshold=<seconds>] [--preferred_voices=<voice1>,<voice2>] [--clean_up=<True/False>] [--pyannote_model=<model_name>] [--diarization_system_instructions=<instructions>] [--translation_system_instructions=<instructions>] [--hugging_face_token=<token>] [--gemini_token=<token>] [--model_name=<model_name>] [--temperature=<value>] [--top_p=<value>] [--top_k=<value>] [--max_output_tokens=<value>] [--elevenlabs_token=<token>] [--use_elevenlabs=<value>]
    ```

3.  **Configuration:** (Optional)
    *   Customize settings for speaker diarization, translation, voice selection, and more using the command-line flags.

## References

*   **DEMUCS:** [https://github.com/facebookresearch/demucs](https://github.com/facebookresearch/demucs)
*   **pyannote:** [https://github.com/pyannote/pyannote-audio](https://github.com/pyannote/pyannote-audio)
*   **faster-whisper:** [https://github.com/SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper)
*   **ElevenLabs:** [https://elevenlabs.io/docs/introduction](https://elevenlabs.io/docs/introduction)
