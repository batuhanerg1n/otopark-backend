from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
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
    status: str

class ParkInfo(BaseModel):
    type: Optional[str] = None
    address: Optional[str] = None
    capacity: Optional[int] = None
    hours: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    services: Optional[dict] = None

class ParkingUpdate(BaseModel):
    park_id: str
    name: str
    total_slots: int
    empty_slots: int
    full_slots: int
    occupancy_rate: float
    slots: list[SlotInfo]
    timestamp: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    info: Optional[ParkInfo] = None


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
        "lat":            data.lat,
        "lng":            data.lng,
        "info":           data.info.dict() if data.info else None,
    }
    await broadcast({"event": "update", "park_id": data.park_id, "data": parking_data[data.park_id]})
    return {"ok": True}


@app.get("/status")
def get_all():
    return {
        "parks":       list(parking_data.values()),
        "total_parks": len(parking_data),
        "timestamp":   time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


@app.get("/status/{park_id}")
def get_park(park_id: str):
    if park_id not in parking_data:
        raise HTTPException(status_code=404, detail=f"{park_id} bulunamadi")
    return parking_data[park_id]


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    clients.append(ws)
    await ws.send_text(json.dumps({"event": "init", "data": list(parking_data.values())}))
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in clients:
            clients.remove(ws)