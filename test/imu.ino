// code for imu
#include <Wire.h>
#include "FastIMU.h"

// Set the I2C address for the primary MPU6050 chip on your HW-290 module
#define MPU6050_ADDRESS  0x68

// Define the primary IMU object under the single FastIMU framework
MPU6050 mpu;

// Storage container for calibration offsets
calData calib = { 0 }; 

// Data structures provided by FastIMU to hold the motion readings
AccelData accelData;
GyroData gyroData;

void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10); // Wait for Serial Monitor to open

  Wire.begin();
  Wire.setClock(400000); // Set I2C to fast mode (400kHz)

  Serial.println("--- HW-290 / GY-87 FastIMU Calibrated Motion Test ---");

  // 1. Initialize the sensor
  int err = mpu.init(calib, MPU6050_ADDRESS);
  if (err != 0) {
    Serial.print("MPU6050 initialization failed with error code: ");
    Serial.println(err);
    while (1);
  }
  Serial.println("MPU6050 initialized successfully!");

  // 2. Perform the calibration routine
  Serial.println("\n>>> CRITICAL STEP: Place the sensor completely flat, level, and perfectly still.");
  Serial.println("Calibration starts in 5 seconds...");
  delay(5000); 

  Serial.println("Calibrating Accelerometer & Gyroscope... DO NOT MOVE THE BOARD.");
  
  // This library function calculates the offsets and saves them into the 'calib' structure
  mpu.calibrateAccelGyro(&calib);
  
  Serial.println("Calibration complete! Starting data stream...\n");
  delay(1000);
}

void loop() {
  // Update internal data registers for the IMU
  mpu.update();

  // Pull calibrated data directly into our tracking structures
  mpu.getAccel(&accelData);
  mpu.getGyro(&gyroData);

  // --- Print Calibrated Accelerometer Data ---
  Serial.println("===== CALIBRATED MOTION =====");
  Serial.print("Accel X: "); Serial.print(accelData.accelX);
  Serial.print(" | Y: "); Serial.print(accelData.accelY);
  Serial.print(" | Z: "); Serial.println(accelData.accelZ);
  
  // --- Print Calibrated Gyroscope Data ---
  Serial.print("Gyro  X: "); Serial.print(gyroData.gyroX);
  Serial.print(" | Y: "); Serial.print(gyroData.gyroY);
  Serial.print(" | Z: "); Serial.println(gyroData.gyroZ);

  Serial.println("--------------------------------\n");
  delay(1000); // 1-second update cycle
}