// run 2 motor using motor driver
//--- Motor 1 (Driver 1) Pins ---
const int RPWM_1 = 2;
const int LPWM_1 = 3;
const int R_EN_1 = 4;
const int L_EN_1 = 5;

// --- Motor 2 (Driver 2) Pins ---
const int RPWM_2 = 6;
const int LPWM_2 = 7;
const int R_EN_2 = 8;
const int L_EN_2 = 9;

void setup() {
  // Configure Motor 1 control pins as outputs
  pinMode(RPWM_1, OUTPUT);
  pinMode(LPWM_1, OUTPUT);
  pinMode(R_EN_1, OUTPUT);
  pinMode(L_EN_1, OUTPUT);

  // Configure Motor 2 control pins as outputs
  pinMode(RPWM_2, OUTPUT);
  pinMode(LPWM_2, OUTPUT);
  pinMode(R_EN_2, OUTPUT);
  pinMode(L_EN_2, OUTPUT);

  // Enable both directions on Driver 1
  digitalWrite(R_EN_1, HIGH);
  digitalWrite(L_EN_1, HIGH);

  // Enable both directions on Driver 2
  digitalWrite(R_EN_2, HIGH);
  digitalWrite(L_EN_2, HIGH);
}

void loop() {
  // 1. Move both Motors Forward at half speed (150 out of 255)
  analogWrite(LPWM_1, 0);
  analogWrite(RPWM_1, 150);
  analogWrite(LPWM_2, 0);
  analogWrite(RPWM_2, 150);
  delay(3000);

  // 2. Brake / Stop both Motors completely
  analogWrite(RPWM_1, 0);
  analogWrite(LPWM_1, 0);
  analogWrite(RPWM_2, 0);
  analogWrite(LPWM_2, 0);
  delay(1000);

  // 3. Move both Motors Backward at half speed
  analogWrite(RPWM_1, 0);
  analogWrite(LPWM_1, 150);
  analogWrite(RPWM_2, 0);
  analogWrite(LPWM_2, 150);
  delay(3000);

  // 4. Brake / Stop both Motors completely
  analogWrite(RPWM_1, 0);
  analogWrite(LPWM_1, 0);
  analogWrite(RPWM_2, 0);
  analogWrite(LPWM_2, 0);
  delay(1000);
}