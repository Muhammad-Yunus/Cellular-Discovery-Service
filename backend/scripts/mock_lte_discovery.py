#!/usr/bin/env python3
"""Mock CLI for lte-discovery that returns fake cell data for testing."""
import json
import sys
import time
import random
from datetime import datetime

def main():
    port = None
    json_output = False
    
    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ('--port', '-p') and i + 1 < len(args):
            port = args[i + 1]
            i += 2
        elif args[i] in ('--json', '-j'):
            json_output = True
            i += 1
        elif args[i] == 'scan':
            i += 1
        else:
            i += 1
    
    # Simulate some delay
    time.sleep(0.5)
    
    # Generate fake cell data based on port
    fake_cells = [
        {
            "operator_name": "Telkomsel",
            "mcc": "510",
            "mnc": "10",
            "rat": "LTE",
            "status": "AVAILABLE",
            "cell_id": f"0x{random.randint(0x10000, 0xFFFFF):05X}",
            "tac": f"0x{random.randint(0x100, 0xFFFF):04X}",
            "pci": random.randint(0, 503),
            "frequency": 1800 + random.randint(0, 200),
            "bandwidth": 10,
            "rssi": -85 + random.randint(-20, 10),
        },
        {
            "operator_name": "Indosat",
            "mcc": "510",
            "mnc": "01",
            "rat": "LTE",
            "status": "AVAILABLE",
            "cell_id": f"0x{random.randint(0x10000, 0xFFFFF):05X}",
            "tac": f"0x{random.randint(0x100, 0xFFFF):04X}",
            "pci": random.randint(0, 503),
            "frequency": 900 + random.randint(0, 100),
            "bandwidth": 5,
            "rssi": -90 + random.randint(-15, 5),
        },
        {
            "operator_name": "XL",
            "mcc": "510",
            "mnc": "11",
            "rat": "LTE",
            "status": "AVAILABLE",
            "cell_id": f"0x{random.randint(0x10000, 0xFFFFF):05X}",
            "tac": f"0x{random.randint(0x100, 0xFFFF):04X}",
            "pci": random.randint(0, 503),
            "frequency": 2100 + random.randint(0, 100),
            "bandwidth": 5,
            "rssi": -92 + random.randint(-15, 5),
        },
    ]
    
    # Add some GSM and UMTS cells
    if random.random() > 0.3:
        fake_cells.append({
            "operator_name": "Telkomsel",
            "mcc": "510",
            "mnc": "10",
            "rat": "GSM",
            "status": "AVAILABLE",
            "cell_id": f"0x{random.randint(0x10000, 0xFFFFF):05X}",
            "lac": f"0x{random.randint(0x1000, 0xFFFF):04X}",
            "arfcn": random.randint(0, 1023),
            "bsic": random.randint(0, 63),
            "rssi": -88 + random.randint(-10, 10),
        })
    
    if random.random() > 0.5:
        fake_cells.append({
            "operator_name": "Indosat",
            "mcc": "510",
            "mnc": "01",
            "rat": "UMTS",
            "status": "AVAILABLE",
            "cell_id": f"0x{random.randint(0x100000, 0xFFFFFF):06X}",
            "ucac": random.randint(0, 511),
            "pilot_scramble_code": random.randint(0, 511),
            "frequency": 2100 + random.randint(0, 100),
            "rssi": -90 + random.randint(-10, 10),
        })
    
    result = {
        "scan_time": datetime.now().isoformat(),
        "port": port or "/dev/ttyAMA0",
        "results": fake_cells,
        "total_cells_found": len(fake_cells),
    }
    
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Scan complete on {port or '/dev/ttyAMA0'}")
        print(f"Found {len(fake_cells)} cells")
        for cell in fake_cells:
            print(f"  {cell.get('operator_name', 'N/A'):10} | {cell.get('rat', 'N/A'):4} | "
                  f"freq: {cell.get('frequency', 'N/A'):>6} | RSSI: {cell.get('rssi', 'N/A'):>5}")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
