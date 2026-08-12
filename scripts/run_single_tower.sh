#!/bin/bash
# Simulasi mission 1 tower, jarak 50m, radius 50m, speed 5m/s, tanpa timeout

cd /home/pi/Cellular-Discovery-Service/scripts

bash simulate_mission.sh \
  --count 1 \
  --min-dist 50 \
  --max-dist 50 \
  --speed 5 \
  --loiter-radius 50 \
  --name "TEST-1-TOWER-50M"
