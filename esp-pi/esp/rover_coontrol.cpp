// ESP32 + L298N USB Serial Rover Control

int IN1 = 4;
int IN2 = 5;
int IN3 = 12;
int IN4 = 13;

void setup() {
  Serial.begin(115200);

  pinMode(IN1, OUTPUT);
  pinMode(IN2, OUTPUT);
  pinMode(IN3, OUTPUT);
  pinMode(IN4, OUTPUT);

  stopMotors();
  Serial.println("Rover Ready...");
}

void moveForward() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  Serial.println("Forward");
}

void moveBackward() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  Serial.println("Backward");
}

void turnLeft() {
  digitalWrite(IN1, HIGH);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, HIGH);
  Serial.println("Left");
}

void turnRight() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, HIGH);
  digitalWrite(IN3, HIGH);
  digitalWrite(IN4, LOW);
  Serial.println("Right");
}

void stopMotors() {
  digitalWrite(IN1, LOW);
  digitalWrite(IN2, LOW);
  digitalWrite(IN3, LOW);
  digitalWrite(IN4, LOW);
  Serial.println("Stop");
}

void loop() {

  // Wait for a command from Raspberry Pi
  if (Serial.available()) {
    char cmd = Serial.read();

    if (cmd == 'F') moveForward();   // A Button
    if (cmd == 'B') moveBackward();  // B Button
    if (cmd == 'L') turnLeft();      // X Button
    if (cmd == 'R') turnRight();     // Y Button
    if (cmd == 'S') stopMotors();    // Release → Stop
  }

}
