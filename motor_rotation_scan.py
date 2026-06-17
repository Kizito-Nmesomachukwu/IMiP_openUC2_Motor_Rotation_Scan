import serial
import json
import time
import os

# =============================================================================
# openUC2 Automated Sample Rotation Script
# Project: 3D Refractive Index Tomography
# Course:  Innovation Methods in Photonics 2026, University of Jena
# Hardware: Seeed Studio XIAO ESP32-S3 + integrated openUC2 motor driver board
# Motor:    SY20STH20-0604A (NEMA 8 stepper, 1.8 degrees per full step)
# Firmware: openUC2 JSON serial protocol (https://youseetoo.github.io)
# =============================================================================
# What this script does:
# It connects to the openUC2 motor controller over USB, rotates the FEP
# capillary tube (which holds the biological specimen in agarose gel inside
# the water cuvette) through a set number of angular positions, and at each
# position prints a placeholder for the camera capture trigger. Once the HIK
# camera SDK is integrated, the placeholder line is replaced with the actual
# capture command to save a hologram at each angle.
#
# The full set of holograms collected this way feeds into the phase retrieval
# pipeline (pipeline_real_image.py) and eventually the 3D reconstruction.
# =============================================================================

# =============================================================================
# HOW TO USE THIS SCRIPT
# =============================================================================
# 1. Install pyserial if not already installed:
#       pip install pyserial
#
# 2. Plug the XIAO ESP32-S3 into your laptop via USB-C.
#
# 3. Find your COM port:
#    Windows: open Device Manager, expand Ports (COM and LPT),
#             look for USB Serial Device. Note the number e.g. COM3.
#    Linux/Mac: run ls /dev/ttyACM* in terminal.
#
# 4. Update the PORT variable below to match your COM port.
#
# 5. Run the script. It waits 7 seconds for the board to boot,
#    does one test move, then asks you to press Enter before the full scan.
#
# 6. Watch the motor shaft. Each step should be clearly visible.
#    A small piece of tape on the shaft helps track rotation.
# =============================================================================

# =============================================================================
# PARAMETERS: change these to match your setup
# =============================================================================

PORT          = 'COM3'    # USB serial port. Change to match your system.
                          # Windows: 'COM3', 'COM4' etc.
                          # Linux/Mac: '/dev/ttyACM0'

BAUD_RATE     = 115200    # Communication speed. Must match the openUC2 firmware.
                          # Default is always 115200 for openUC2 boards.

STEPPER_ID    = 1         # Which motor axis to use.
                          # openUC2 axis mapping: A=0, X=1, Y=2, Z=3.
                          # Axis 1 (X) confirmed working on our hardware.
                          # If the motor does not move, try STEPPER_ID = 0.

STEPS_PER_REV = 500       # How many steps the firmware needs for one full
                          # 360 degree rotation of the shaft.
                          # This was determined experimentally on our motor.
                          # If your motor overshoots or undershoots a full
                          # rotation, adjust this number up or down.

NUM_ANGLES    = 10        # How many angular positions to image.
                          # 10 angles = 36 degrees per step (good for testing,
                          # very visible rotation).
                          # 36 angles = 10 degrees per step (better for
                          # tomographic reconstruction quality).
                          # 72 or 180 angles for high quality final scans.

MOTOR_SPEED   = 5000      # Rotation speed in steps per second.
                          # Higher = faster. Start at 1000 for smooth motion.
                          # 5000 is fast and works well for dry testing.
                          # For water-filled cuvette: use 1000-2000 to avoid
                          # sloshing that blurs the holograms.

SETTLE_MS     = 800       # Time in milliseconds to wait after each motor step
                          # before triggering the camera.
                          # This is critical: the water in the cuvette vibrates
                          # after the motor steps. If you capture too soon,
                          # the holographic fringes will be blurred and the
                          # phase reconstruction will fail.
                          # Increase to 1200 or 1500 if you see blurry fringes.

SAVE_FOLDER   = "Tomography_Dataset"
                          # Folder where hologram images will be saved.
                          # Created automatically if it does not exist.

# =============================================================================
# CALCULATED VALUES (do not change these)
# =============================================================================

# How many steps the motor takes per angular increment
steps_per_angle = int(STEPS_PER_REV / NUM_ANGLES)

# How many degrees each step corresponds to
angle_per_step  = 360.0 / NUM_ANGLES

print(f"Steps per angle:  {steps_per_angle}")
print(f"Degrees per step: {angle_per_step:.1f}")
print(f"Total angles:     {NUM_ANGLES}")
print(f"Motor speed:      {MOTOR_SPEED} steps/sec")
print(f"Settle time:      {SETTLE_MS} ms")

# =============================================================================
# MOTOR COMMAND FUNCTION
# =============================================================================

def send_move(ser, steps):
    # Build the JSON command that the openUC2 firmware understands.
    # The firmware expects a newline-terminated JSON string over serial.
    # "isabs": 0 means relative move (move BY this many steps from current
    # position), not absolute (move TO a specific position).
    # "isaccel": 0 means no acceleration ramping, constant speed throughout.
    command = {
        "task": "/motor_act",
        "motor": {
            "steppers": [{
                "stepperid": STEPPER_ID,  # which axis to move
                "position":  steps,       # how many steps to move
                "speed":     MOTOR_SPEED, # steps per second
                "isabs":     0,           # 0 = relative move
                "isaccel":   0            # 0 = no acceleration ramp
            }]
        }
    }

    # Send the command over USB serial
    cmd_string = json.dumps(command) + "\n"
    ser.write(cmd_string.encode())

    # Read back the firmware response using readline.
    # We use readline with a deadline instead of ser.in_waiting because
    # the Microsoft USB CDC driver on Windows does not support the
    # ClearCommError() call that in_waiting triggers internally.
    lines    = []
    deadline = time.time() + 2.0
    while time.time() < deadline:
        line = ser.readline()
        if line:
            lines.append(line.decode(errors='ignore').strip())
    return '\n'.join(lines)

# =============================================================================
# MAIN SCAN
# =============================================================================

# Create the output folder if it does not already exist
os.makedirs(SAVE_FOLDER, exist_ok=True)

try:
    # Open the serial connection to the XIAO ESP32-S3.
    # dsrdtr=False and rtscts=False prevent the DTR and RTS control lines
    # from toggling on connection, which would trigger an ESP32 reset and
    # crash the firmware. write_timeout=None means writes block until
    # complete rather than timing out.
    print("\nOpening serial connection...")
    ser = serial.Serial(
        PORT,
        BAUD_RATE,
        timeout       = 1.0,   # read timeout in seconds
        write_timeout = None,  # no write timeout, wait as long as needed
        dsrdtr        = False, # do not toggle DTR on connect
        rtscts        = False  # do not use hardware flow control
    )

    # The ESP32 needs time to finish booting after the serial port opens.
    # 7 seconds is enough to cover the full boot sequence including
    # firmware initialisation and module loading.
    print("Waiting 7 seconds for board to boot...")
    time.sleep(7)
    print("Board ready.\n")

    # Send one test move before the full scan to confirm the motor responds.
    # If the shaft does not move here, check the STEPPER_ID and wiring
    # before proceeding to the full scan.
    print("Test move: sending one angular increment...")
    print("Watch the motor shaft. It should move visibly.")
    resp = send_move(ser, steps_per_angle)
    print(f"Firmware response: {resp}")
    time.sleep(1)

    input("\nIf the motor moved, press Enter to start the full scan...")

    print(f"\nStarting scan: {NUM_ANGLES} angles, {angle_per_step:.1f} degrees each")
    print("-" * 55)

    for i in range(NUM_ANGLES):

        current_angle = i * angle_per_step

        # Step 1: rotate motor by one angular increment
        resp = send_move(ser, steps_per_angle)
        print(f"[{i+1:>2}/{NUM_ANGLES}]  {current_angle:>6.1f} deg  |  {resp[:40]}")

        # Step 2: wait for mechanical and fluid vibrations to settle.
        # This is the most important timing constraint in the whole pipeline.
        # The water in the cuvette sloshes after each motor step. The
        # settle time ensures the fringes are sharp when the camera fires.
        time.sleep(SETTLE_MS / 1000.0)

        # Step 3: trigger camera capture.
        # Replace the print statement below with your actual camera command
        # once the HIK camera SDK or hardware trigger is connected.
        # Example: camera.capture(os.path.join(SAVE_FOLDER, filename))
        filename = f"Hologram_Angle_{current_angle:.1f}.png"
        print(f"         --> Capture: {filename}")

    print("-" * 55)
    print(f"\nScan complete. {NUM_ANGLES} holograms captured.")
    print(f"Images saved to: {SAVE_FOLDER}/")

except Exception as e:
    print(f"\nError: {e}")

finally:
    # Always close the serial port, even if the scan crashed.
    # If the port is not closed, it stays locked and the next run
    # will fail with a PermissionError. If this happens, restart
    # the Jupyter kernel to release the port.
    try:
        ser.close()
        print("Serial port closed.")
    except:
        pass
