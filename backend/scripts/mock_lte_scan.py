#!/usr/bin/env python3
"""Mock CLI for lte-scan that returns fake cell data for testing."""
import json
import sys
import time
import random
from datetime import datetime

def main():
    band = None
    json_output = False
    gain = None
    
    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] in ('--band', '-b') and i + 1 < len(args):
            band = args[i + 1]
            i += 2
        elif args[i] in ('--json', '-j'):
            json_output = True
            i += 1
        elif args[i] in ('--gain', '-g') and i + 1 < len(args):
            gain = args[i + 1]
            i += 2
        elif args[i].isdigit():
            # First positional arg is band
            band = args[i]
            i += 1
        else:
            i += 1
    
    # Simulate some delay
    time.sleep(0.3)
    
    # Generate fake cell data for the band
    band_freq_map = {
        "5": {"freq_start": 1710, "freq_end": 1790, "earfcn_range": (10560, 10919)},
        "8": {"freq_start": 824, "freq_end": 894, "earfcn_range": (512, 876)},
    }
    
    freq_info = band_freq_map.get(band, {"freq_start": 1800, "freq_end": 1900, "earfcn_range": (0, 10000)})
    
    fake_cells = []
    
    # Generate 2-5 cells per band
    num_cells = random.randint(2, 5)
    operators = [
        {"name": "Telkomsel", "mcc": "510", "mnc": "10"},
        {"name": "Indosat", "mcc": "510", "mnc": "01"},
        {"name": "XL", "mcc": "510", "mnc": "11"},
        {"name": "Tri", "mcc": "510", "mnc": "89"},
    ]
    
    for _ in range(num_cells):
        op = random.choice(operators)
        earfcn = random.randint(*freq_info["earfcn_range"])
        freq_mhz = freq_info["freq_start"] + random.uniform(0, freq_info["freq_end"] - freq_info["freq_start"])
        
        fake_cells.append({
            "operator_name": op["name"],
            "mcc": op["mcc"],
            "mnc": op["mnc"],
            "rat": "LTE",
            "status": "AVAILABLE",
            "earfcn": str(earfcn),
            "pci": random.randint(0, 503),
            "frequency_mhz": round(freq_mhz, 2),
            "rsrp": round(-120 + random.uniform(0, 40), 1),
            "band": band,
        })
    
    result = {
        "scan_time": datetime.now().isoformat(),
        "band": band,
        "gain_db": gain,
        "cells": fake_cells,
        "scan_info": {
            "total_cells": len(fake_cells),
            "duration_ms": int(random.uniform(500, 1500)),
        },
    }
    
    if json_output:
        print(json.dumps(result, indent=2))
    else:
        print(f"Scan complete on band {band} (gain={gain}dB)")
        print(f"Found {len(fake_cells)} cells")
        for cell in fake_cells:
            print(f"  {cell.get('operator_name', 'N/A'):10} | PCI: {cell.get('pci', 'N/A'):>3} | "
                  f"EARFCN: {cell.get('earfcn', 'N/A'):>6} | RSRP: {cell.get('rsrp', 'N/A'):>7} dBm")
    
    sys.exit(0)

if __name__ == "__main__":
    main()
