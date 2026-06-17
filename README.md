# openUC2 Automated Sample Rotation

Project: 3D Refractive Index Tomography

Course: Innovation Methods in Photonics 2026, University of Jena

Hardware: Seeed Studio XIAO ESP32-S3 + openUC2 motor driver board

Motor: SY20STH20-0604A (NEMA 8 stepper)

## What this does

This script controls the motorised sample rotation stage of an openUC2
Mach-Zehnder interferometer setup for 3D holographic tomography. It rotates
a biological specimen held in a FEP capillary tube through a set of angular
positions, pausing at each position to allow camera capture of an off-axis
hologram.

The collected holograms are processed by the phase retrieval pipeline in
the companion repository to produce 2D phase maps, which are then stacked
into a 3D refractive index volume.

## Requirements
pip install pyserial
## Hardware setup

1. Plug the XIAO ESP32-S3 into your laptop via USB-C
2. Find your COM port in Device Manager (Windows) or /dev/ttyACM0 (Linux/Mac)
3. Update PORT in the script to match

## Key parameters

| Parameter | Default | What it does |
|-----------|---------|-------------|
| PORT | COM3 | USB serial port of the XIAO |
| STEPPER_ID | 1 | Motor axis (X=1 confirmed on our hardware) |
| STEPS_PER_REV | 500 | Steps for one full 360 degree rotation |
| NUM_ANGLES | 10 | Number of angular positions to capture |
| MOTOR_SPEED | 5000 | Steps per second (reduce to 1000 for water-filled cuvette) |
| SETTLE_MS | 800 | Wait time after each step for vibrations to settle |

## Important notes

Do not send the motor enable command (isen:1) separately.
It causes a firmware crash on this board version. Motor power
is handled automatically by the move commands.

Do not use ser.in_waiting on Windows with the Microsoft USB CDC
driver. It triggers a ClearCommError that crashes the serial
connection. This script uses readline() with a deadline instead.
