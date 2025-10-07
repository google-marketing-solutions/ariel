from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from transcribe import router as transcribe_router

app = FastAPI()

templates = Jinja2Templates(directory="templates")
app.include_router(transcribe_router)


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
