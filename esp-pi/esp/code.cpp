int led = 2;  // built-in LED on some boards, or connect an LED here

void setup() {
  Serial.begin(115200);
  pinMode(led, OUTPUT);
}

void loop() {
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');

    if (cmd == "ON") {
      digitalWrite(led, HIGH);
    }

    if (cmd == "OFF") {
      digitalWrite(led, LOW);
    }
  }
}
