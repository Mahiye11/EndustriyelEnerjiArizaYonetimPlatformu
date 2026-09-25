from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

DB_PATH = Path(os.getenv("DATABASE_PATH", "/tmp/factorypulse.db"))
JWT_SECRET = os.getenv("JWT_SECRET", "local-development-secret").encode()


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def initialize() -> None:
    with db() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS devices (
              id TEXT PRIMARY KEY, factory_id TEXT NOT NULL, line_name TEXT NOT NULL,
              name TEXT NOT NULL, power_threshold REAL NOT NULL, temperature_threshold REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS measurements (
              measurement_id TEXT PRIMARY KEY, device_id TEXT NOT NULL, factory_id TEXT NOT NULL,
              recorded_at TEXT NOT NULL, power_kw REAL NOT NULL, temperature_c REAL NOT NULL,
              running INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_measurements_device_time
              ON measurements(device_id, recorded_at DESC);
            CREATE TABLE IF NOT EXISTS alarms (
              id TEXT PRIMARY KEY, device_id TEXT NOT NULL, factory_id TEXT NOT NULL,
              kind TEXT NOT NULL, value REAL NOT NULL, threshold REAL NOT NULL,
              status TEXT NOT NULL, assignee TEXT, created_at TEXT NOT NULL, resolved_at TEXT
            );
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO devices VALUES (?, ?, ?, ?, ?, ?)",
            ("machine-42", "factory-istanbul", "Hat A", "CNC Freze 42", 20.0, 75.0),
        )


class LoginRequest(BaseModel):
    email: str
    password: str


class DeviceCreate(BaseModel):
    id: str = Field(min_length=2, max_length=80)
    factoryId: str
    lineName: str
    name: str
    powerThreshold: float = Field(gt=0)
    temperatureThreshold: float = Field(gt=0)


class ThresholdUpdate(BaseModel):
    powerKw: float = Field(gt=0)
    temperatureC: float = Field(gt=0)


class MeasurementIn(BaseModel):
    measurementId: UUID
    deviceId: str
    recordedAt: datetime
    powerKw: float = Field(ge=0)
    temperatureC: float
    running: bool


class Assignment(BaseModel):
    technician: str = Field(min_length=2)


class SocketHub:
    def __init__(self) -> None:
        self.clients: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, factory_id: str, socket: WebSocket) -> None:
        await socket.accept()
        self.clients[factory_id].add(socket)

    def disconnect(self, factory_id: str, socket: WebSocket) -> None:
        self.clients[factory_id].discard(socket)

    async def publish(self, factory_id: str, event: dict[str, Any]) -> None:
        dead = []
        for socket in self.clients[factory_id]:
            try:
                await socket.send_json(event)
            except RuntimeError:
                dead.append(socket)
        for socket in dead:
            self.disconnect(factory_id, socket)


hub = SocketHub()


def encode_token(subject: str, role: str, factory_id: str) -> str:
    payload = {"sub": subject, "role": role, "factoryId": factory_id, "exp": int(time.time()) + 86400}
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature = hmac.new(JWT_SECRET, body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def decode_token(token: str) -> dict[str, Any]:
    try:
        body, signature = token.split(".")
        expected = hmac.new(JWT_SECRET, body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if payload["exp"] < time.time():
            raise ValueError
        return payload
    except (ValueError, KeyError, json.JSONDecodeError):
        raise HTTPException(401, "Invalid or expired token")


def current_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Bearer token required")
    return decode_token(authorization.removeprefix("Bearer "))


def row_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(row)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize()
    yield


app = FastAPI(title="FactoryPulse API", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(HTTPException)
async def http_error(_, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": f"HTTP_{exc.status_code}", "message": str(exc.detail), "requestId": str(uuid4())},
    )


@app.get("/health")
def health():
    return {"status": "ok", "time": utcnow()}


@app.post("/api/v1/auth/login")
def login(body: LoginRequest):
    if body.password != "factorypulse" or body.email not in {
        "admin@factorypulse.local", "operator@factorypulse.local", "tech@factorypulse.local"
    }:
        raise HTTPException(401, "Email or password is incorrect")
    role = "admin" if body.email.startswith("admin") else "technician" if body.email.startswith("tech") else "operator"
    return {"accessToken": encode_token(body.email, role, "factory-istanbul"), "role": role, "factoryId": "factory-istanbul"}


@app.get("/api/v1/auth/me")
def me(user=Depends(current_user)):
    return user


@app.get("/api/v1/devices")
def devices(user=Depends(current_user)):
    with db() as connection:
        return [row_dict(row) for row in connection.execute("SELECT * FROM devices WHERE factory_id=? ORDER BY name", (user["factoryId"],))]


@app.post("/api/v1/devices", status_code=201)
def create_device(body: DeviceCreate, user=Depends(current_user)):
    if user["role"] != "admin" or body.factoryId != user["factoryId"]:
        raise HTTPException(403, "Admin access to this factory is required")
    try:
        with db() as connection:
            connection.execute("INSERT INTO devices VALUES (?, ?, ?, ?, ?, ?)", (body.id, body.factoryId, body.lineName, body.name, body.powerThreshold, body.temperatureThreshold))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "Device already exists")
    return body


@app.put("/api/v1/devices/{device_id}/thresholds")
def update_thresholds(device_id: str, body: ThresholdUpdate, user=Depends(current_user)):
    if user["role"] != "admin":
        raise HTTPException(403, "Admin role required")
    with db() as connection:
        result = connection.execute("UPDATE devices SET power_threshold=?, temperature_threshold=? WHERE id=? AND factory_id=?", (body.powerKw, body.temperatureC, device_id, user["factoryId"]))
        if not result.rowcount:
            raise HTTPException(404, "Device not found")
    return {"deviceId": device_id, **body.model_dump()}


@app.post("/api/v1/measurements", status_code=202)
async def ingest(body: MeasurementIn, x_device_key: str | None = Header(default=None)):
    if x_device_key != "demo-device-key":
        raise HTTPException(401, "Valid X-Device-Key required")
    with db() as connection:
        device = connection.execute("SELECT * FROM devices WHERE id=?", (body.deviceId,)).fetchone()
        if not device:
            raise HTTPException(404, "Device not found")
        existing = connection.execute("SELECT * FROM measurements WHERE measurement_id=?", (str(body.measurementId),)).fetchone()
        if existing:
            return {"accepted": True, "duplicate": True, "measurement": row_dict(existing)}
        measurement = (str(body.measurementId), body.deviceId, device["factory_id"], body.recordedAt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"), body.powerKw, body.temperatureC, int(body.running))
        connection.execute("INSERT INTO measurements VALUES (?, ?, ?, ?, ?, ?, ?)", measurement)
        created_alarms = []
        checks = (("power", body.powerKw, device["power_threshold"]), ("temperature", body.temperatureC, device["temperature_threshold"]))
        for kind, value, threshold in checks:
            if value <= threshold:
                continue
            open_alarm = connection.execute("SELECT id FROM alarms WHERE device_id=? AND kind=? AND status!='resolved'", (body.deviceId, kind)).fetchone()
            if not open_alarm:
                alarm = {"id": str(uuid4()), "device_id": body.deviceId, "factory_id": device["factory_id"], "kind": kind, "value": value, "threshold": threshold, "status": "open", "assignee": None, "created_at": utcnow(), "resolved_at": None}
                connection.execute("INSERT INTO alarms VALUES (:id,:device_id,:factory_id,:kind,:value,:threshold,:status,:assignee,:created_at,:resolved_at)", alarm)
                created_alarms.append(alarm)
    event = {"eventId": str(uuid4()), "eventType": "measurement.received", "occurredAt": utcnow(), "factoryId": device["factory_id"], "deviceId": body.deviceId, "payload": body.model_dump(mode="json")}
    await hub.publish(device["factory_id"], event)
    for alarm in created_alarms:
        await hub.publish(device["factory_id"], {"eventId": str(uuid4()), "eventType": "alarm.created", "occurredAt": utcnow(), "factoryId": device["factory_id"], "deviceId": body.deviceId, "payload": alarm})
    return {"accepted": True, "duplicate": False, "alarmsCreated": len(created_alarms)}


@app.get("/api/v1/devices/{device_id}/measurements")
def history(device_id: str, from_: str | None = Query(default=None, alias="from"), to: str | None = None, limit: int = Query(100, ge=1, le=500), user=Depends(current_user)):
    clauses, args = ["device_id=?", "factory_id=?"], [device_id, user["factoryId"]]
    if from_: clauses.append("recorded_at>=?"); args.append(from_)
    if to: clauses.append("recorded_at<=?"); args.append(to)
    args.append(limit)
    with db() as connection:
        rows = connection.execute(f"SELECT * FROM measurements WHERE {' AND '.join(clauses)} ORDER BY recorded_at DESC LIMIT ?", args).fetchall()
    return [row_dict(row) for row in rows]


@app.get("/api/v1/alarms")
def alarms(status: str | None = None, user=Depends(current_user)):
    query, args = "SELECT * FROM alarms WHERE factory_id=?", [user["factoryId"]]
    if status: query += " AND status=?"; args.append(status)
    with db() as connection:
        return [row_dict(row) for row in connection.execute(query + " ORDER BY created_at DESC", args)]


@app.post("/api/v1/alarms/{alarm_id}/assign")
async def assign(alarm_id: str, body: Assignment, user=Depends(current_user)):
    with db() as connection:
        result = connection.execute("UPDATE alarms SET assignee=?, status='assigned' WHERE id=? AND factory_id=? AND status!='resolved'", (body.technician, alarm_id, user["factoryId"]))
        if not result.rowcount: raise HTTPException(404, "Open alarm not found")
    await hub.publish(user["factoryId"], {"eventType": "alarm.assigned", "alarmId": alarm_id, "technician": body.technician})
    return {"id": alarm_id, "status": "assigned", "assignee": body.technician}


@app.post("/api/v1/alarms/{alarm_id}/resolve")
async def resolve(alarm_id: str, user=Depends(current_user)):
    if user["role"] not in {"technician", "admin"}: raise HTTPException(403, "Technician role required")
    with db() as connection:
        result = connection.execute("UPDATE alarms SET status='resolved', resolved_at=? WHERE id=? AND factory_id=? AND status!='resolved'", (utcnow(), alarm_id, user["factoryId"]))
        if not result.rowcount: raise HTTPException(404, "Open alarm not found")
    await hub.publish(user["factoryId"], {"eventType": "alarm.resolved", "alarmId": alarm_id})
    return {"id": alarm_id, "status": "resolved"}


@app.get("/api/v1/reports/energy")
def energy_report(from_: str = Query(alias="from"), to: str = Query(), user=Depends(current_user)):
    with db() as connection:
        summary = connection.execute("SELECT COUNT(*) samples, COALESCE(AVG(power_kw),0) average_power_kw, COALESCE(MAX(power_kw),0) peak_power_kw FROM measurements WHERE factory_id=? AND recorded_at BETWEEN ? AND ?", (user["factoryId"], from_, to)).fetchone()
        alarm_count = connection.execute("SELECT COUNT(*) count FROM alarms WHERE factory_id=? AND created_at BETWEEN ? AND ?", (user["factoryId"], from_, to)).fetchone()["count"]
    return {**row_dict(summary), "alarm_count": alarm_count, "from": from_, "to": to}


@app.websocket("/ws/factories/{factory_id}")
async def realtime(socket: WebSocket, factory_id: str, token: str = Query()):
    user = decode_token(token)
    if user["factoryId"] != factory_id:
        await socket.close(code=1008); return
    await hub.connect(factory_id, socket)
    try:
        while True: await socket.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(factory_id, socket)

