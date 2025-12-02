import serial
from inputs import get_gamepad

ser = serial.Serial('/dev/ttyACM0', 115200)

print("Listening for gamepad...")

while True:
    events = get_gamepad()
    for e in events:

        if e.code == "BTN_SOUTH" and e.state == 1:
            ser.write(b"ON\n")
            print("LED ON sent")

        if e.code == "BTN_EAST" and e.state == 1:
            ser.write(b"OFF\n")
            print("LED OFF sent")
        
        if e.code == "BTN_WEST" and e.state == 1:
            print("Exit requested. Closing script...")
            ser.close()
            exit()