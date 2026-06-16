import asyncio
import json
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from simulator.app.core.virtual_machine import VirtualMachine

router = APIRouter()

class ScanRequest(BaseModel):
    barcode: str
    scenario: str = "HAPPY_PATH"
    protocol: str = "ASTM"

@router.post("/scan")
async def simulate_scan(request: ScanRequest):
    vm = VirtualMachine()
    logs = []
    success = False
    async for event_type, message in vm.run_simulation(request.protocol, request.scenario, request.barcode):
        logs.append(f"[{event_type}] {message}")
        if event_type == "success":
            success = True
            
    return {
        "status": "success" if success else "error",
        "message": logs[-1] if logs else "No simulation logs generated",
        "logs": logs
    }

@router.get("/stream")
async def simulate_stream(
    barcode: str,
    scenario: str = "HAPPY_PATH",
    protocol: str = "ASTM",
    host: str = "127.0.0.1",
    port: int = 5601,
    test_code: str = "WBC",
    test_val: str = "7.5",
    test_unit: str = "10^3/uL"
):
    async def event_generator():
        vm = VirtualMachine(host=host, port=port)
        custom_results = None
        if scenario == "RESULT_UPLOAD" or protocol == "HL7":
            custom_results = {
                "code": test_code,
                "val": test_val,
                "unit": test_unit
            }
            
        async for event_type, message in vm.run_simulation(protocol, scenario, barcode, custom_results):
            data = json.dumps({"type": event_type, "message": message})
            yield f"data: {data}\n\n"
            await asyncio.sleep(0.05) # Yield control to let it stream smoothly

    return StreamingResponse(event_generator(), media_type="text/event-stream")
