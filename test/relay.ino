// code for relay
const int relayPin = 7; // Connect relay IN to digital pin 7

void setup() {
  pinMode(relayPin, OUTPUT);
  // Set initial state to HIGH (turns relay OFF for active-low modules)
  digitalWrite(relayPin, HIGH); 
}

void loop() {
  digitalWrite(relayPin, LOW);  // Turn relay ON
  delay(1000);                  // Wait for 1 second
  
  digitalWrite(relayPin, HIGH); // Turn relay OFF
  delay(1000);                  // Wait for 1 second
}