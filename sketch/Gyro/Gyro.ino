/*
The sensor outputs provided by the library are the raw 16-bit values
obtained by concatenating the 8-bit high and low gyro data registers.
They can be converted to units of dps (degrees per second) using the
conversion factors specified in the datasheet for your particular
device and full scale setting (gain).

Example: An L3GD20H gives a gyro X axis reading of 345 with its
default full scale setting of +/- 245 dps. The So specification
in the L3GD20H datasheet (page 10) states a conversion factor of 8.75
mdps/LSB (least significant bit) at this FS setting, so the raw
reading of 345 corresponds to 345 * 8.75 = 3020 mdps = 3.02 dps.
*/

#include <Wire.h>
#include <L3G.h>
#include <Timer.h>
// #include <SoftwareSerial.h>

#define DEBUG 0

// Pin numbers
const int PIN_TRIGGER    = 2;   // laser gun trigger input
const int PIN_BT_STATE   = 3;   // bluetooth state input
const int PIN_RED_LED    = 4;   // red LED to indicate pairing state
// const int PIN_BLUE_LED   = 5;   // blue LED to indicate trigger
const int PIN_BLUE_LED = 13;
const int PIN_GREEN_LED  = 6;   // green LED to indicate ready state
const int PIN_RFI        = 7;   // single shot or rapid fire mode

// const int PIN_BT_RX      = 8;   // bluetooth serial RX
// const int PIN_BT_TX      = 9;   // bluetooth serial TX

// constant periods
const unsigned long T_READ     = 10;  // period for gyro update
const unsigned long T_BTSTATE  = 207; // period for bluetotoh state updtae
const unsigned long T_SEND     = 200; // period for sending position to client
const unsigned long T_RFI      = 97;  // period for rapid fire mode update (and indicator LED)

//SoftwareSerial bluetooth(PIN_BT_RX, PIN_BT_TX); 
L3G            gyro;
Timer          timer;

// gyro variables
float dscale = (float)T_READ / 1000.0f * 2.0; // conversion to degrees per second
float off_x, off_y, off_z;                    // calibration offsets
float px, py, pz;                             // absolute estimated positions

// bluetooth variables
int          btState   = 0;       // 0 = connecting, 1 = ready
volatile int btChanged = 1;       // state pin change since last update
String       btMsg = "";          // a string to hold incoming data
boolean      btMsgValid = false;  // whether the string is complete

// state vairables 
boolean running = false;     // send updates?
boolean trigger = false;     // trigger pressed
boolean rapidfire = false;   // rapid fire switch enabled
boolean triggerSend = false; // send trigger status update 
boolean rfiSend = false;     // send rapid fire mode update
char    greenShade = 0;      // PWM value for green LED (pulsates in rapid fire mode)

void setup() {
  pinMode(PIN_TRIGGER, INPUT_PULLUP);
  pinMode(PIN_RFI, INPUT_PULLUP);
  pinMode(PIN_BT_STATE, INPUT);
  pinMode(PIN_BLUE_LED, OUTPUT);
  pinMode(PIN_RED_LED, OUTPUT);
  pinMode(PIN_GREEN_LED, OUTPUT);
  
  attachInterrupt(1, btStateChange, CHANGE);
  attachInterrupt(0, triggerChange, CHANGE);
  
  digitalWrite(PIN_RED_LED, 1);
  digitalWrite(PIN_BLUE_LED, 0);
  digitalWrite(PIN_GREEN_LED, 0);
  
  Serial.begin(115200);
  Wire.begin();

  // setup gyrometer
  if (!gyro.init()) {
    // Serial.println("Failed to autodetect gyro type!");
    // FIXME: indicate failure by blinking LED or something
    while (1);
  }
  gyro.enableDefault();  
  px = .0f;
  py = .0f;
  pz = .0f;
  calibrate();
  
  // setup timer
  timer.every(T_READ, updateGyro);
  timer.every(T_BTSTATE, updateState);
  timer.every(T_SEND, sendUpdate);
  timer.every(T_RFI, updateRFI);
  // timer.every(1000, dump);
  
  // bluetooth.begin(9600);
}

/* void dump(){
  Serial.print("STATE = ");
  Serial.println(btState);    
} */

void calibrate() {
  int t = 25;
  int n = 10;

  off_x = .0f;
  off_y = .0f;
  off_z = .0f;
 
  for (int i=0; i<n; ++i){
    gyro.read();
    off_x += gyro.g.x;
    off_y += gyro.g.y;
    off_z += gyro.g.z;
    delay(t);
  } 
  off_x /= n;
  off_y /= n;
  off_z /= n;  
}

void btStateChange() {
  btChanged = 1;
}

void triggerChange() {
  trigger = !digitalRead(PIN_TRIGGER);
  triggerSend = true;  
}

void updateState(){
  
  // bluetooth connection state
  if (btChanged){
    btState = 0;
    digitalWrite(PIN_RED_LED, 1);
    digitalWrite(PIN_GREEN_LED, 0);
  } else {
    btState = 1;
    digitalWrite(PIN_RED_LED, 0);
  }
  btChanged = 0;
}

void updateRFI(){
  
  // rapid fire mode
  if (btState == 1){ 
    boolean rfiRead = !digitalRead(PIN_RFI);
    rfiSend = rfiRead ^ rapidfire;
    rapidfire = rfiRead;
    if (rapidfire){
      greenShade = greenShade + 25;
      analogWrite(PIN_GREEN_LED, greenShade);
    } else {
      digitalWrite(PIN_GREEN_LED, 1);
    }  
  }
}


void loop() {
  timer.update(); 
  
  if (triggerSend){
    triggerSend = false;
    digitalWrite(PIN_BLUE_LED, trigger ? 1 : 0);
    if (running){
      if (trigger){
        Serial.println("TRG ON");
        Serial.flush();
      } else {
        Serial.println("TRG OFF");
        Serial.flush();
      }
    }    
  }
  if (rfiSend){
    rfiSend = false;
    if (running){
      if (rapidfire){
        Serial.println("RFI ON");
        Serial.flush();
      } else {
        Serial.println("RFI OFF");
        Serial.flush();
      }
    }    
  } 
  
  bluetoothListen();
  
  if (btMsgValid){
    btMsgValid = false; 
    if (btMsg == "GET"){
      printGyro();
      
      // FIXME: send trigger and mode
    } else if (btMsg == "RST"){
      px = .0f;
      py = .0f;
      pz = .0f;
      Serial.println("RST OK");
    } else if (btMsg == "CAL"){
      calibrate();      
      Serial.println("CAL OK");
    } else if (btMsg == "RUN"){
       running = true;
       Serial.println("RUN OK");
    } else if (btMsg == "STP"){
       running = false;
       Serial.println("STP OK");
    }
    btMsg = "";
  }
}


void updateGyro(){
  gyro.read();
  
  float dx = (gyro.g.x - off_x) * 8.75/1000.0;
  float dy = (gyro.g.y - off_y) * 8.75/1000.0;
  float dz = (gyro.g.z - off_z) * 8.75/1000.0;
  
  px += dx * dscale;
  py += dy * dscale;
  pz += dz * dscale;
}

void bluetoothListen(){
  while (Serial.available()) {
    
    // get the new byte and append to message
    char inChar = (char)Serial.read();
    if (inChar == '\n') {
      btMsgValid = true;
    } else {
      btMsg += inChar;
    }
  }  
}

void sendUpdate(){
  if (running){
    printGyro();
  }  
}

void printGyro(){
  Serial.print("POS ");
  Serial.print(px);
  Serial.print(",");
  Serial.print(py);
  Serial.print(",");
  Serial.println(pz);
  Serial.flush();
}
