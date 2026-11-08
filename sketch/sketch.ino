#include "Arduino_RouterBridge.h"
#include <CNCShield.h>
#include <AccelStepper.h>
#include <Servo.h>
#include "Arduino_LED_Matrix.h"
#include "Animation.h"

Arduino_LED_Matrix matrix;

// ============================================================
// CNC SHIELD
// ============================================================

CNCShield cnc_shield;

StepperMotor *motorX;
StepperMotor *motorY;
StepperMotor *motorZ;

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
// FIXED MOTOR SPEEDS
// ============================================================

const float X_SPEED = 50.0;
const float Y_SPEED = 50.0;
const float Z_SPEED = 50.0;
const float A_SPEED = 50.0;

// ============================================================
// CURRENT MOTOR STATE (-1, 0, 1)
// ============================================================

int directionX = 0;
int directionY = 0;
int directionZ = 0;
int directionA = 0;

// ============================================================
// ACCELSTEPPER CALLBACKS
// ============================================================

void xForward()  { motorX->step(CLOCKWISE); }
void xBackward() { motorX->step(COUNTER); }

void yForward()  { motorY->step(CLOCKWISE); }
void yBackward() { motorY->step(COUNTER); }

void zForward()  { motorZ->step(CLOCKWISE); }
void zBackward() { motorZ->step(COUNTER); }

AccelStepper stepperX(xForward, xBackward);
AccelStepper stepperY(yForward, yBackward);
AccelStepper stepperZ(zForward, zBackward);
AccelStepper stepperA(AccelStepper::DRIVER, A_STEP_PIN, A_DIR_PIN);

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

  cnc_shield.begin();

  motorX = cnc_shield.get_motor(0);
  motorY = cnc_shield.get_motor(1);
  motorZ = cnc_shield.get_motor(2);

  stepperX.setMaxSpeed(X_SPEED);
  stepperY.setMaxSpeed(Y_SPEED);
  stepperZ.setMaxSpeed(Z_SPEED);
  stepperA.setMaxSpeed(A_SPEED);

  stepperX.setSpeed(0);
  stepperY.setSpeed(0);
  stepperZ.setSpeed(0);
  stepperA.setSpeed(0);

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
}

// ============================================================
// MAIN LOOP — must run continuously to pulse steps
// ============================================================

void loop() {

  // Plays through one iteration of the loaded sequence using the per-frame delay (500 ms)
  matrix.playSequence();
  stepperX.runSpeed();
  stepperY.runSpeed();
  stepperZ.runSpeed();
  stepperA.runSpeed();
  // servo is positional — no per-loop update needed, it just
  // holds whatever angle it was last commanded to
}

// ============================================================
// SET MOTOR (direction: -1, 0, 1) — X and Y, independent
// ============================================================

void set_motor_x(int direction) {
  direction = clampDirection(direction);
  directionX = direction;
  stepperX.setSpeed(directionX * X_SPEED);
}

void set_motor_y(int direction) {
  direction = clampDirection(direction);
  directionY = direction;
  stepperY.setSpeed(directionY * Y_SPEED);
}

// ============================================================
// JOINT CONTROL — Z and A face each other and must counter-
// rotate to move the shared link in one direction.
// ============================================================

void set_joint_za(int direction) {
  direction = clampDirection(direction);

  directionZ = direction;
  directionA = -direction;   // A always spins opposite to Z

  stepperZ.setSpeed(directionZ * Z_SPEED);
  stepperA.setSpeed(directionA * A_SPEED);
}

void stop_joint_za() {
  directionZ = 0;
  directionA = 0;
  stepperZ.setSpeed(0);
  stepperA.setSpeed(0);
}

int get_joint_za() {
  return directionZ;
}

// ============================================================
// STOP INDIVIDUAL MOTORS (X, Y only — Z/A stop via joint)
// ============================================================

void stop_motor_x() {
  directionX = 0;
  stepperX.setSpeed(0);
}

void stop_motor_y() {
  directionY = 0;
  stepperY.setSpeed(0);
}

// ============================================================
// STOP ALL
// ============================================================

void stop_all() {
  stop_motor_x();
  stop_motor_y();
  stop_joint_za();
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
// HELPER
// ============================================================

int clampDirection(int direction) {
  if (direction > 0) return 1;
  if (direction < 0) return -1;
  return 0;
}