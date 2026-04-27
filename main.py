"""
Akilli Otopark - FastAPI Backend
----------------------------------
detector.py buraya POST atar, web/mobil buradan okur.

Endpoints:
  POST /update          → detector.py'den veri al
  GET  /status          → tum otoparkların durumu
  GET  /status/{park_id}→ tek otopark durumu
  WS   /ws              → gercek zamanli websocket
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import asyncio
import json
import time

app = FastAPI(title="Akilli Otopark API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


parking_data: dict = {}


clients: list[WebSocket] = []



class SlotInfo(BaseModel):
    id: int
    status: str  # "empty" | "occupied"

class ParkingUpdate(BaseModel):
    park_id: str
    name: str
    total_slots: int
    empty_slots: int
    full_slots: int
    occupancy_rate: float
    slots: list[SlotInfo]
    timestamp: Optional[str] = None



async def broadcast(data: dict):
    disconnected = []
    for ws in clients:
        try:
            await ws.send_text(json.dumps(data))
        except:
            disconnected.append(ws)
    for ws in disconnected:
        clients.remove(ws)




@app.get("/")
def root():
    return {"message": "Akilli Otopark API calisiyor", "version": "1.0"}


@app.post("/update")
async def update_parking(data: ParkingUpdate):
    """detector.py her saniye buraya POST atar."""
    parking_data[data.park_id] = {
        "park_id":        data.park_id,
        "name":           data.name,
        "total_slots":    data.total_slots,
        "empty_slots":    data.empty_slots,
        "full_slots":     data.full_slots,
        "occupancy_rate": data.occupancy_rate,
        "slots":          [s.dict() for s in data.slots],
        "timestamp":      data.timestamp or time.strftime("%Y-%m-%dT%H:%M:%S"),
        "last_seen":      time.time(),
    }
    
    await broadcast({"event": "update", "park_id": data.park_id, "data": parking_data[data.park_id]})
    return {"ok": True}


@app.get("/status")
def get_all():
    """Tum otoparkların durumu."""
    return {
        "parks":       list(parking_data.values()),
        "total_parks": len(parking_data),
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


@app.get("/status/{park_id}")
def get_park(park_id: str):
    """Tek otopark durumu."""
    if park_id not in parking_data:
        raise HTTPException(status_code=404, detail=f"{park_id} bulunamadi")
    return parking_data[park_id]


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Gercek zamanli baglanti — frontend buraya baglanir."""
    await ws.accept()
    clients.append(ws)
    
    await ws.send_text(json.dumps({"event": "init", "data": list(parking_data.values())}))
    try:
        while True:
            await ws.receive_text()   
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)
