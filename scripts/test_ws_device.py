#!/usr/bin/env python3
"""Quick WebSocket test for /ws/device/location"""
import asyncio
import json
import sys

WS_URL = "ws://localhost:8001/ws/device/location"


async def test_ws():
    import websockets
    print(f"Connecting to {WS_URL} ...")
    async with websockets.connect(WS_URL) as ws:
        print("✅ Connected!")
        for i in range(5):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=8)
                data = json.loads(msg)
                loc = data.get("data", {})
                print(f"[{i+1}] lat={loc.get('latitude'):.6f}, lon={loc.get('longitude'):.6f}, "
                      f"alt={loc.get('altitude')}, course={loc.get('course_deg')}, "
                      f"speed={loc.get('speed')} m/s, status={loc.get('status')}")
            except asyncio.TimeoutError:
                print(f"[{i+1}] Timeout waiting for message")
                break
        print("Done!")


if __name__ == "__main__":
    asyncio.run(test_ws())
