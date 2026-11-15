// run 1 motor with encoder using motor driver
//Define PWM speed control pins
const int RPWM_Pin = 5;
const int LPWM_Pin = 6;

// Define Enable pins
const int R_EN_Pin = 7;
const int L_EN_Pin = 8;

// Define Encoder Pins (A3 and A4 can be read as digital pins)
const int ENCODER_A = A3;
const int ENCODER_B = A4;

// Variables to track encoder position
volatile long encoderCount = 0;
int lastStateA;

// Variables for non-blocking timing (replaces delay)
unsigned long previousMillis = 0;
int motorStep = 1; // Tracks current movement phase (1 to 4)

void setup() {
  pinMode(RPWM_Pin, OUTPUT);
  pinMode(LPWM_Pin, OUTPUT);
  pinMode(R_EN_Pin, OUTPUT);
  pinMode(L_EN_Pin, OUTPUT);

  // Set encoder pins as inputs (using internal pullup if encoder lacks them)
  pinMode(ENCODER_A, INPUT_PULLUP);
  pinMode(ENCODER_B, INPUT_PULLUP);

  // Enable both directions on the driver
  digitalWrite(R_EN_Pin, HIGH);
  digitalWrite(L_EN_Pin, HIGH);

  // Initialize Serial Monitor to view the count
  Serial.begin(9600);
  
  // Read initial state of Encoder A
  lastStateA = digitalRead(ENCODER_A);
}

void loop() {
  // --- 1. CONTINUOUS ENCODER READING ---
  int currentStateA = digitalRead(ENCODER_A);
  
  // Check if a pulse/edge occurred on Channel A
  if (currentStateA != lastStateA) {
    // If Channel B is different than Channel A, the motor is moving in one direction
    if (digitalRead(ENCODER_B) != currentStateA) {
      encoderCount++;
    } else {
      encoderCount--;
    }
    
    // Print the absolute position to the serial monitor
    Serial.print("Position: ");
    Serial.println(encoderCount);
  }
  lastStateA = currentStateA; // Update state tracking


  // --- 2. NON-BLOCKING STATE MACHINE FOR MOTOR CONTROL ---
  unsigned long currentMillis = millis();

  switch (motorStep) {
    case 1: // Move Forward at half speed for 3000ms
      analogWrite(LPWM_Pin, 0);
      analogWrite(RPWM_Pin, 150);
      if (currentMillis - previousMillis >= 3000) {
        previousMillis = currentMillis;
        motorStep = 2; // Transition to step 2
      }
      break;

    case 2: // Brake / Stop the motor completely for 1000ms
      analogWrite(RPWM_Pin, 0);
      analogWrite(LPWM_Pin, 0);
      if (currentMillis - previousMillis >= 1000) {
        previousMillis = currentMillis;
        motorStep = 3;
      }
      break;

    case 3: // Move Backward at half speed for 3000ms
      analogWrite(RPWM_Pin, 0);
      analogWrite(LPWM_Pin, 150);
      if (currentMillis - previousMillis >= 3000) {
        previousMillis = currentMillis;
        motorStep = 4;
      }
      break;

    case 4: // Brake / Stop the motor completely for 1000ms
      analogWrite(RPWM_Pin, 0);
      analogWrite(LPWM_Pin, 0);
      if (currentMillis - previousMillis >= 1000) {
        previousMillis = currentMillis;
        motorStep = 1; // Loop back to step 1
      }
      break;
  }
}