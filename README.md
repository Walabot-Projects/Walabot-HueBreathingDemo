# Breath Monitoring Application with Philips Hue

Python example code to demonstrate Walabot breathing monitor, using a Philips Hue lamp.

This example shows how to capture and use the Walabot energy reading for breath monitoring. The breathing rate is indicated by the change of brightness of a Philips Hue Lamp. As breathing slows, the lamp will also change color from blue to red.

In the example it is also shown how to use multiprocessing and zmq to create a Walabot server and client. Using this code structure the Walabot can collect data on a remote device (ie. Raspberry Pi), with the processing taking place on another machine.	

### Required Python Libraries

* WalabotAPI
* phue
* zmq

### Using the code

Before running, set the Philips Hue bridge IP address and Hue lamp name at the beginning of the code.

Set the Walabot in a vertical orientation in front of you chest. 

If it is the first time connecting to the Philips bridge, you will be asked to press the 'Philips' key on bridge and then press any key on the computer.

Pressing the up and down keys will increase or decrease, respectively, the amount of samples used to assess breathing intensity and rate. More samples yield a smother yet slower response of the light. Less samples will result in a faster yet less stable response of the light. Pressing the space bar will return the samples amount to the default number, set in the beginning of the code.

Press the 'q' button to quit the demo.

### How the code works

The code is built of two threads; The Walabot server thread, responsible for operating the Walabot. The main program thread, responsible for tracking the breathing and operating the Hue lamp. Communications between the threads is done by the zmq library using a REQUEST-RESPONSE model. 

The Walabot server initializes the Walabot, sets the profile and arena and listens to requests from the client. For breath monitoring the SENSOR_NARROW profile, optimized for energy tracking, is used. The arena is set for a narrow and near scan, as it assumed the person being monitored is sitting in front of the sensor. Finally, the main loop is constantly triggering the Walabot, captures movement energy readings and when receiving the appropriate command, send the reading to the client.

The main thread connects to the Philips Hue bridge, gets energy reading from the Walabot server and controls the lamp according to the breathing pattern. The main loop collects energy reading into a list of samples. The last three samples are averaged and the breath level is determined relative to the sample with the maximum value. The lamp brightness is set according to the breath level. The time of each breath peak is logged. As the time from the last breath peak gets longer the hue of the lamp is turned redder.   
