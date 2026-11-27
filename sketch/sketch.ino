#include "Arduino_RouterBridge.h"
#include <CNCShield.h>
#include <Servo.h>
#include "Arduino_LED_Matrix.h"
#include "Animation.h"

Arduino_LED_Matrix matrix;

// ============================================================
// CNC SHIELD
// ============================================================

CNCShield cnc_shield;

StepperMotor *motorX; // X-axis (Driver 1)
StepperMotor *motorY; // Y-axis (Driver 2)
StepperMotor *motorZ; // Z-axis (Driver 3 - Shoulder Side 1)

// ============================================================
// A AXIS — driven directly, bypassing CNCShield (library only
// supports 3 motors). Standard CNC Shield V3 A-axis pins.
// ============================================================

#define A_STEP_PIN 12
#define A_DIR_PIN  13

// ============================================================
// SERVO (180° positional, standard servo) — gripper open/close
// ============================================================

#define SERVO_PIN 9

const int SERVO_OPEN_ANGLE  = 0;
const int SERVO_CLOSE_ANGLE = 180;

Servo gripperServo;
int servoAngle = SERVO_OPEN_ANGLE;  // current angle, for UI state

// ============================================================
// MOTOR STEP TIMING (smaller = faster, in microseconds)
// ============================================================

const int STEP_DELAY_US = 1500;

unsigned long lastStepMicrosX = 0;
unsigned long lastStepMicrosY = 0;
unsigned long lastStepMicrosZ = 0;
unsigned long lastStepMicrosA = 0;

// ============================================================
// CURRENT MOTOR STATE (-1, 0, 1)
// ============================================================

int directionX = 0;
int directionY = 0;
int directionZ = 0;
int directionA = 0;
int pumpState = 0;

// ============================================================
// SETUP
// ============================================================

void setup() {
  Bridge.begin();   // must come first, before any Bridge.provide()

  // Initialize the onboard 8x13 LED matrix
  matrix.begin();

  // Load the animation sequence into the matrix buffer
  matrix.loadSequence(animation);

  pinMode(A_STEP_PIN, OUTPUT);
  pinMode(A_DIR_PIN, OUTPUT);
  digitalWrite(A_STEP_PIN, LOW);
  digitalWrite(A_DIR_PIN, LOW);

  cnc_shield.begin();
  cnc_shield.enable(); // Enables all 4 drivers (Pin 8 LOW)

  motorX = cnc_shield.get_motor(0);
  motorY = cnc_shield.get_motor(1);
  motorZ = cnc_shield.get_motor(2);

  gripperServo.attach(SERVO_PIN);
  gripperServo.write(servoAngle);

  Bridge.provide("set_motor_x", set_motor_x);
  Bridge.provide("set_motor_y", set_motor_y);

  Bridge.provide("set_joint_za", set_joint_za);
  Bridge.provide("stop_joint_za", stop_joint_za);
  Bridge.provide("get_joint_za", get_joint_za);

  Bridge.provide("stop_motor_x", stop_motor_x);
  Bridge.provide("stop_motor_y", stop_motor_y);

  Bridge.provide("stop_all", stop_all);

  Bridge.provide("get_motor_x", get_motor_x);
  Bridge.provide("get_motor_y", get_motor_y);

  Bridge.provide("set_servo_angle", set_servo_angle);
  Bridge.provide("get_servo_angle", get_servo_angle);

  // Compatibility wrappers for high-level rover commands
  Bridge.provide("drive", bridge_drive);
  Bridge.provide("arm", bridge_arm);
  Bridge.provide("pump", bridge_pump);
}

// ============================================================
// MAIN LOOP — must run continuously to pulse steps
// ============================================================

void loop() {

  // Plays through one iteration of the loaded sequence using the per-frame delay (500 ms)
  matrix.playSequence();

  unsigned long now = micros();

  if (directionX != 0 && (now - lastStepMicrosX >= (unsigned long)STEP_DELAY_US)) {
    lastStepMicrosX = now;
    motorX->step();
  }

  if (directionY != 0 && (now - lastStepMicrosY >= (unsigned long)STEP_DELAY_US)) {
    lastStepMicrosY = now;
    motorY->step();
  }

  if (directionZ != 0 && (now - lastStepMicrosZ >= (unsigned long)STEP_DELAY_US)) {
    lastStepMicrosZ = now;
    motorZ->step();
  }

  if (directionA != 0 && (now - lastStepMicrosA >= (unsigned long)STEP_DELAY_US)) {
    lastStepMicrosA = now;
    digitalWrite(A_STEP_PIN, HIGH);
    delayMicroseconds(10);
    digitalWrite(A_STEP_PIN, LOW);
  }

  // servo is positional — no per-loop update needed, it just
  // holds whatever angle it was last commanded to
}

// ============================================================
// SET MOTOR (direction: -1, 0, 1) — X and Y, independent
// ============================================================

void set_motor_x(int direction) {
  direction = clampDirection(direction);
  directionX = direction;
  if (directionX > 0) {
    motorX->set_dir(CLOCKWISE);
  } else if (directionX < 0) {
    motorX->set_dir(COUNTER);
  }
}

void set_motor_y(int direction) {
  direction = clampDirection(direction);
  directionY = direction;
  if (directionY > 0) {
    motorY->set_dir(CLOCKWISE);
  } else if (directionY < 0) {
    motorY->set_dir(COUNTER);
  }
}

// ============================================================
// JOINT CONTROL — Z and A face each other and must counter-
// rotate to move the shared link in one direction.
// ============================================================

void set_joint_za(int direction) {
  direction = clampDirection(direction);

  directionZ = direction;
  directionA = -direction;   // A always spins opposite to Z

  if (direction > 0) {
    motorZ->set_dir(CLOCKWISE);
    digitalWrite(A_DIR_PIN, LOW);   // Opposite of Z
  } else if (direction < 0) {
    motorZ->set_dir(COUNTER);
    digitalWrite(A_DIR_PIN, HIGH);  // Opposite of Z
  }
}

void stop_joint_za() {
  directionZ = 0;
  directionA = 0;
}

int get_joint_za() {
  return directionZ;
}

// ============================================================
// STOP INDIVIDUAL MOTORS (X, Y only — Z/A stop via joint)
// ============================================================

void stop_motor_x() {
  directionX = 0;
}

void stop_motor_y() {
  directionY = 0;
}

// ============================================================
// STOP ALL
// ============================================================

void stop_all() {
  stop_motor_x();
  stop_motor_y();
  stop_joint_za();
  pumpState = 0;
  // servo has no "stop" concept now — it just holds position
}

// ============================================================
// GET STATE
// ============================================================

int get_motor_x() { return directionX; }
int get_motor_y() { return directionY; }

// ============================================================
// SERVO CONTROL (180° positional gripper)
// ============================================================

void set_servo_angle(int angle) {
  if (angle < 0) angle = 0;
  if (angle > 180) angle = 180;   // clamped to your 0-150 working range
  servoAngle = angle;
  gripperServo.write(servoAngle);
}

int get_servo_angle() {
  return servoAngle;
}

// ============================================================
// HIGH-LEVEL BRIDGE WRAPPERS
// ============================================================

void bridge_drive(float left, float right) {
  int dirL = (left > 0.15f) ? 1 : ((left < -0.15f) ? -1 : 0);
  int dirR = (right > 0.15f) ? 1 : ((right < -0.15f) ? -1 : 0);
  set_motor_x(dirL);
  set_motor_y(dirR);
}

void bridge_arm(int base, int shoulder, int elbow) {
  (void)base;
  if (shoulder > 90) {
    set_joint_za(1);
  } else if (shoulder < 90) {
    set_joint_za(-1);
  } else {
    stop_joint_za();
  }
  set_servo_angle(elbow);
}

void bridge_pump(int on) {
  pumpState = (on != 0) ? 1 : 0;
}

// ============================================================
// HELPER
// ============================================================

int clampDirection(int direction) {
  if (direction > 0) return 1;
  if (direction < 0) return -1;
  return 0;
}