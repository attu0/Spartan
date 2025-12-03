import serial
from inputs import get_gamepad

ser = serial.Serial('/dev/ttyACM0', 115200)

print("Rover control started...")

while True:
    events = get_gamepad()
    for e in events:

        # A = Forward
        if e.code == "BTN_SOUTH":
            if e.state == 1:
                ser.write(b"F\n")
                print("Forward")
            else:
                ser.write(b"S\n")

        # B = Backward
        if e.code == "BTN_EAST":
            if e.state == 1:
                ser.write(b"B\n")
                print("Backward")
            else:
                ser.write(b"S\n")

        # X = Left
        if e.code == "BTN_WEST":
            if e.state == 1:
                ser.write(b"L\n")
                print("Left")
            else:
                ser.write(b"S\n")

        # Y = Right
        if e.code == "BTN_NORTH":
            if e.state == 1:
                ser.write(b"R\n")
                print("Right")
            else:
                ser.write(b"S\n")
