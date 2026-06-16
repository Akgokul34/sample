import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from simulator.app.api.v1 import simulate

app = FastAPI(title="LIC Simulator API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simulate.router, prefix="/api/v1/simulate", tags=["Simulator"])

app.mount("/", StaticFiles(directory="simulator/static", html=True), name="static")

if __name__ == "__main__":
    uvicorn.run("simulator.main:app", host="0.0.0.0", port=8001, reload=True)
