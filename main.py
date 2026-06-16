import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from backend.app.api.v1 import patients, machines, results
import asyncio
import os
from backend.app.communication.tcp_server import TCPServer
from backend.app.communication.astm.state_machine import ASTMStateMachine

app = FastAPI(title="LIC Platform API", version="1.0.0")


tcp_task = None
hl7_task = None

from backend.app.core.database import Base, engine
from backend.app.models import patient, machine, dictionary, result

@app.on_event("startup")
async def startup_event():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    global tcp_task, hl7_task
    
    async def astm_connection_handler(reader, writer):
        # Create a new state machine instance for EVERY connection
        handler = ASTMStateMachine()
        await handler.handle_connection(reader, writer)
        
    server = TCPServer(host="0.0.0.0", port=5601, protocol_handler=astm_connection_handler)
    tcp_task = asyncio.create_task(server.start())
    
    from backend.app.communication.hl7.mllp import mllp_handler
    hl7_server = TCPServer(host="0.0.0.0", port=5602, protocol_handler=mllp_handler)
    hl7_task = asyncio.create_task(hl7_server.start())

@app.on_event("shutdown")
async def shutdown_event():
    if tcp_task:
        tcp_task.cancel()
    if hl7_task:
        hl7_task.cancel()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.environ.get("LIC_CORS_ORIGINS", "http://localhost:8000").split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
app.include_router(machines.router, prefix="/api/v1/machines", tags=["Machines"])
app.include_router(results.router, prefix="/api/v1/results", tags=["Results"])

app.mount("/", StaticFiles(directory="backend/static", html=True), name="static")

@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
