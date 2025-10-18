import os
import shutil
import uuid
import json
from fastapi.responses import FileResponse
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from dubble.configuration import DubbleConfig
import dubble_logic
import logging
logger = logging.getLogger('uvicorn.error')
logger.setLevel(logging.DEBUG)



# --- App Initialization ---
app = FastAPI(title="Dubble: You AI Dubbing Service")

# Setup directories
UPLOADS_DIR = "uploads"
OUTPUTS_DIR = "outputs"
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(OUTPUTS_DIR, exist_ok=True)

# Mount static files to serve generated audio/video
app.mount("/outputs", StaticFiles(directory=OUTPUTS_DIR), name="outputs")
templates = Jinja2Templates(directory="templates")

# In-memory storage for job state. For production, use a database like Redis.
JOB_STATE = {}

# --- API Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main HTML user interface."""
    config = dubble_logic.DubbleConfig()
    return templates.TemplateResponse("index.html", {"request": request, "default_prompts": config.prompt_library})

@app.post("/clean-outputs")
async def clean_outputs():
    """Deletes all files and subdirectories in the outputs directory."""
    logger.info(f"Cleaning up {OUTPUTS_DIR} and {UPLOADS_DIR} directories.")
    try:
        for filename in os.listdir(OUTPUTS_DIR):
            file_path = os.path.join(OUTPUTS_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}. Reason: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to delete {file_path}. Reason: {e}")
            
        for filename in os.listdir(UPLOADS_DIR):
            file_path = os.path.join(UPLOADS_DIR, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}. Reason: {e}")
                raise HTTPException(status_code=500, detail=f"Failed to delete {file_path}. Reason: {e}")
            
        return JSONResponse({"status": "success", "message": "Outputs & Uploas directory cleaned."})
    except Exception as e:
        logger.error(f"Error cleaning outputs directory: {e}")
        raise HTTPException(status_code=500, detail=f"Error cleaning outputs directory: {e}")


@app.post("/start-process")
async def start_process(
    request: Request,
    # Basic params
    original_language: str = Form(...),
    target_language: str = Form(...),
    gcp_project: str = Form(...),
    gcp_project_location: str = Form(...),
    video_file: UploadFile = File(None),
    gcs_path: str = Form(None),
    brand_name: str = Form(...),
    # Advanced Models
    analysis_model: str = Form(...),
    embedding_model: str = Form(...),
    tts_model: str = Form(...),
    # Advanced Temps
    analysis_temperature: float = Form(...),
    translation_temperature: float = Form(...),
    tts_temperature: float = Form(...),
    # Advanced Speed
    max_speed_up_ratio: float = Form(...),
    feature_speed_up_enable: bool = Form(...),
    # Advanced Refinement
    max_refinement_attempts: int = Form(...),
    feature_refinement_enable: bool = Form(...),
    # Advanced Other
    max_concurrent_threads: int = Form(...),
    prompt_edit: bool = Form(...),
    # Advanced Prompts
    prompt_diarization: str = Form(...),
    prompt_translation: str = Form(...),
    prompt_translation_refinement: str = Form(...),
    tts_prompt_template: str = Form(...),
    script: str = Form(...),
    workflow: str = Form(...),
):
    """STAGE 1: Receives video and config, runs analysis, and returns utterances."""
    job_id = str(uuid.uuid4())
    job_dir = os.path.join(OUTPUTS_DIR, job_id)
    
    os.makedirs(job_dir, exist_ok=True)

    file_path = None
    if video_file and video_file.filename:
        file_path = os.path.join(UPLOADS_DIR, f"{job_id}_{video_file.filename}")
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(video_file.file, buffer)
    elif gcs_path:
        file_path = os.path.join(UPLOADS_DIR, f"{job_id}_{gcs_path.split("/")[-1]}")
        file_path = dubble_logic.download_from_gcs(gcs_url=gcs_path, file_path=file_path)
    
    if not file_path:
        raise HTTPException(status_code=400, detail="No video file or GCS path provided.")

    config_params = {
        "gcp_project": gcp_project,
        "gcp_project_location" : gcp_project_location,
        "original_language": original_language,
        "target_language": target_language,
        "video_file_path": file_path,
        "brand_name": brand_name,
        "analysis_model": analysis_model,
        "embedding_model": embedding_model,
        "tts_model": tts_model,
        "analysis_temperature": analysis_temperature,
        "translation_temperature": translation_temperature,
        "tts_temperature": tts_temperature,
        "max_speed_up_ratio": max_speed_up_ratio,
        "feature_speed_up_enable": feature_speed_up_enable,
        "max_refinement_attempts": max_refinement_attempts,
        "feature_refinement_enable": feature_refinement_enable,
        "max_concurrent_threads": max_concurrent_threads,
        "prompt_edit": prompt_edit,
        "prompt_library": {
            "diarization": prompt_diarization,
            "translation": prompt_translation,
            "translation_refinement": prompt_translation_refinement,
            "tts_prompt_template": tts_prompt_template,
        },
        "output_local_path" : job_dir,
        "script" : script
    }

    try:

        
        config = DubbleConfig(**json.loads(dubble_logic.initialize(config_params)))
        
        if workflow == "dub":
        
            utterances  = dubble_logic.diarize(config)
            JOB_STATE[job_id] = {
                "config": config,
                "utterances": utterances,
                "approved_audio": [None] * len(utterances)
            } 
        
        else: 
            utterances = dubble_logic.create_default_utterances(config)
            JOB_STATE[job_id] = {
                "config": config,
                "utterances": utterances,
                "approved_audio": [[""]]
            }
        
            

        return JSONResponse({
            "job_id": job_id,
            "utterances": utterances,
            "voice_options": list(config.VOICE_OPTIONS.keys()),
            "sync_modes": config.SYNC_MODES,
            "video_url": f"download/{config.video_file_path.split('/')[-1]}"
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error {e}") 

@app.post("/translate-utterance")
async def generate_speech(
    job_id: str = Form(...),
    index: int = Form(...),
    utterance: str = Form(...),
    ):
    """Translates the original text from source language to target."""
    
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
 
    state = JOB_STATE[job_id]

    utterance = json.loads(utterance)
    try:
        new_translated_text = dubble_logic.translate_utterance(utterance, state["config"])
        utterance["translated_text"] = new_translated_text
        
        state["utterances"][index] = utterance

        return JSONResponse({"translated_text": new_translated_text,
                             "original_text": utterance["original_text"],
                             "source_language": utterance["source_language"],
                             "target_language": utterance["target_language"]})    
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error {e}") 



@app.post("/generate-speech")
async def generate_speech(
    job_id: str = Form(...),
    index: int = Form(...),
    utterance: str = Form(...)
):
    """STAGE 2: Generates audio for a single utterance."""
    
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
 
    state = JOB_STATE[job_id]
    job_dir = os.path.join(OUTPUTS_DIR, job_id)
    # Adding a new utterance when cloning an existing one

    if index + 1 > len(state["utterances"]):
        state["utterances"].append({})

    utterance = json.loads(utterance)
    
    
    try:
        audio_path, new_translated_text = dubble_logic.generate_single_utterance_speech(utterance, state["config"], job_dir)
        utterance["audio_url"] = f"/outputs/{job_id}/{os.path.basename(audio_path)}"
        utterance["translated_text"] = new_translated_text
        logger.debug(f"Main received generated speech {utterance}")
        state["utterances"][index] = utterance

        return JSONResponse({"audio_url": f"/outputs/{job_id}/{os.path.basename(audio_path)}",
                             "translated_text": new_translated_text,
                             "original_text": utterance["original_text"]})    
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error {e}") 


@app.post("/approve-speech")
async def approve_speech(
    job_id: str = Form(...),
    index: int = Form(...),
    audio_path: str = Form(...) # The filename of the approved audio
):
    """Marks an utterance's audio as approved."""
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
        
    state = JOB_STATE[job_id]
    job_dir = os.path.join(OUTPUTS_DIR, job_id)
    full_audio_path = os.path.join(job_dir, audio_path)
    
    if not os.path.exists(full_audio_path):
        raise HTTPException(status_code=404, detail="Approved audio file not found.")

    state["approved_audio"][index] = full_audio_path
    return JSONResponse({"status": "approved"})

@app.post("/add-utterance")
async def add_utterance(job_id: str = Form(...), index = Form(...), utterance: str = Form(...)):
   
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
    
    state = JOB_STATE[job_id]
    
 
    if int(index) + 1 > len(state["utterances"]):
        state["utterances"].append(json.loads(utterance))
    else:
        state["utterances"].insert(int(index), json.loads(utterance))

    return JSONResponse({
        "status": "OK"
    })

@app.post("/update-utterance")
async def update_utterance(job_id: str = Form(...), index = Form(...), utterance: str = Form(...)):
   
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
    
    state = JOB_STATE[job_id]

    if int(index) + 1 > len(state["utterances"]):
        state["utterances"].append(json.loads(utterance))
    else:
        state["utterances"][int(index)] = json.loads(utterance)
    
    return JSONResponse({
    "status": "OK"
    })

@app.post("/remove-utterance")
async def remove_utterance(job_id: str = Form(...), utterance_id: str = Form(...)):
   
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
    
    state = JOB_STATE[job_id]
    
    utterances = state["utterances"]
    utterances.pop(int(utterance_id))

    return JSONResponse({
        "utterance_id": utterance_id
    })

@app.post("/assemble-video")
async def assemble_video(job_id: str = Form(...),
                         updated_utterances: str = Form(...),
                         music_volume: float = Form(...),
                         speech_volume: float = Form(...)
                         ):
    """STAGE 3: Assembles the final video from all approved audio clips."""
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")
    
    try:
        updated_utterances = json.loads(updated_utterances)

        state = JOB_STATE[job_id]
        approved_audio = state["approved_audio"]
        config = state["config"]
        utterances = state["utterances"]
        config.music_volume = float(music_volume) / 100
        config.speech_volume = float(speech_volume) / 100

        #if None in approved_audio:
        #    raise HTTPException(status_code=400, detail="Not all utterances have approved audio.")
        
        for (index, utterance) in enumerate(utterances):

            if index < len(updated_utterances):
                duration = float(utterance["end"]) - float(utterance["start"])
                utterance["start"] = float(updated_utterances[index]["start"])
                utterance["end"] = utterance["start"] + duration
                
            else:
                utterances.pop(index)
        
        state["utterances"] = utterances
        final_video_path = dubble_logic.assemble_final_video(utterances, config)
        
        
        return JSONResponse({
            "video_url": f"download/{os.path.basename(final_video_path)}"
        })
    
    except Exception as e:
        logger.error(f"Error while processing the video {e}")
        raise HTTPException(status_code=500, detail=f"Error {e}")


@app.get("/download/{filename}")
def download(filename: str):
    path = f"uploads/{filename}"
    headers = {"Cache-Control": "no-cache"} 
    return FileResponse(path=path, filename=filename, headers=headers) # provide filename, media_type is optional

@app.post("/apply-to-single-video")
async def apply_to_single_video(
    job_id: str = Form(...),
    video_url: str = Form(...),
    music_volume: float = Form(...),
    speech_volume: float = Form(...)
):
    if job_id not in JOB_STATE:
        raise HTTPException(status_code=404, detail="Job not found")

    state = JOB_STATE[job_id]
    config = state["config"]
    utterances = state["utterances"]

    config.music_volume = float(music_volume) / 100
    config.speech_volume = float(speech_volume) / 100

    try:
        # 1. Download video from GCS
        file_path = dubble_logic.download_from_gcs(video_url, UPLOADS_DIR)

        # 2. Update config with new video path
        config.video_file_path = file_path

        # 3. Assemble video
        final_video_path = dubble_logic.assemble_final_video(utterances, config)

        # 4. Upload the assembled video to GCS
        dubbed_gcs_url = dubble_logic.upload_to_gcs(final_video_path, video_url)

        return JSONResponse({"status": "success", "video_url": video_url, "dubbed_url": dubbed_gcs_url})

    except Exception as e:
        logger.error(f"Failed to process video {video_url}. Reason: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process video {video_url}. Reason: {e}")
