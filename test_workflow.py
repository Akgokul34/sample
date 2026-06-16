import urllib.request
import json
import time

def main():
    print("=== Step 1: Register a Patient ===")
    patient_data = {
        "mrn": "MRN-TEST-100",
        "first_name": "Alice",
        "last_name": "Smith",
        "dob": "1990-01-01"
    }
    req = urllib.request.Request(
        "http://localhost:8000/api/v1/patients/",
        data=json.dumps(patient_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            patient = json.loads(response.read().decode())
            print("Patient Registered:", patient)
            patient_id = patient["id"]
    except Exception as e:
        print("Failed to register patient:", e)
        return

    print("\n=== Step 2: Create an Order ===")
    order_data = {
        "accession_number": "ACC-TEST-100"
    }
    req = urllib.request.Request(
        f"http://localhost:8000/api/v1/patients/{patient_id}/orders",
        data=json.dumps(order_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            order = json.loads(response.read().decode())
            print("Order Created:", order)
    except Exception as e:
        print("Failed to create order:", e)
        return

    print("\n=== Step 3: Run ASTM Host Query Simulation ===")
    scan_data = {
        "barcode": "ACC-TEST-100",
        "scenario": "HAPPY_PATH",
        "protocol": "ASTM"
    }
    req = urllib.request.Request(
        "http://localhost:8001/api/v1/simulate/scan",
        data=json.dumps(scan_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            scan_res = json.loads(response.read().decode())
            print("ASTM Scan Response:", json.dumps(scan_res, indent=2))
    except Exception as e:
        print("Failed to run ASTM scan:", e)

    print("\n=== Step 4: Run ASTM Result Upload Simulation ===")
    result_scan_data = {
        "barcode": "ACC-TEST-100",
        "scenario": "RESULT_UPLOAD",
        "protocol": "ASTM"
    }
    req = urllib.request.Request(
        "http://localhost:8001/api/v1/simulate/scan",
        data=json.dumps(result_scan_data).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as response:
            scan_res = json.loads(response.read().decode())
            print("ASTM Result Upload Response:", json.dumps(scan_res, indent=2))
    except Exception as e:
        print("Failed to run ASTM result upload:", e)

    print("\n=== Step 5: Check Saved Test Results ===")
    time.sleep(1) # Wait for db commit
    try:
        with urllib.request.urlopen("http://localhost:8000/api/v1/results/") as response:
            results = json.loads(response.read().decode())
            print("Results in DB:", json.dumps(results, indent=2))
    except Exception as e:
        print("Failed to check results:", e)

if __name__ == "__main__":
    main()
