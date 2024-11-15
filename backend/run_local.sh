#!/bin/bash
PORT=8888
pip install -r requirements.txt
gunicorn -b 0.0.0.0:$PORT -t 600 -w 1 app:app
