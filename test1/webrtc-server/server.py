# server.py
import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

offer_store = None

@app.post("/offer")
async def offer(request: Request):
    global offer_store
    offer_store = await request.json()
    return {"status": "offer-received"}

@app.get("/offer")
async def get_offer():
    return offer_store

answer_store = None

@app.post("/answer")
async def answer(request: Request):
    global answer_store
    answer_store = await request.json()
    return {"status": "answer-received"}

@app.get("/answer")
async def get_answer():
    return answer_store


@app.get("/")
async def index():
    return HTMLResponse(open("static/index.html").read())
