```ino 
#include <SoftwareSerial.h>
SoftwareSerial(10, 9); // RX  on arduino (10) -> TX of the BT module, BT of the arduino (9) -> RX of the BT 

void setup () {
    bt.begin(38400); // factory default
    serial.begin(9600); // we can also use a different boadrate
}

void loop () {
    if (serial.available()){
        bt.write(serial.read());
    }

    if (bt.available()){
        serial.print(bt.readString());
    }
}

/*
 
 ** upload the program to arduino UNO 
 ** choose the boad rate, not necessarily 9600 but would be good
 ** if you find New line -> Change it to Both NL & CR on the serial monitor (if it reads New Line or Return)
 ** Better done before entering the BT config mode

*/



/* 

** How to exit the config mode **
** Just power cycle without the BT module's button pressed

*/

```