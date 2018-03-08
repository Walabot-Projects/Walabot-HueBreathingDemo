'''
    hue_breathing_demo.py

    Example code to demonstrate Walabot breathing monitor,
    using a Philips Hue lamp.

    This example shows how to capture and use the Walabot
    energy reading for breath monitoring. The breathing rate
    is indicated by the change of brightness of a Philips Hue
    Lamp. As breathing slows, the lamp will also change color
    from blue to red.

    In the example it is also shown how to use multiprocessing
    and zmq to create a Walabot server and client. Using this
    code structure the Walabot can collect data on a remote
    device (ie. Raspberry Pi), with the processing taking
    place on another machine.

    Before running set the Philips Hue bridge IP address and
    Hue lamp name in the code below.

    Required Python libraries:
        - WalabotAPI
        - zmq
        - phue

    Created on 3 Jan 2018

    @author: Ohad Tzafrir <ohad.tzafrir@vayyar.com>
'''

import multiprocessing
import time
import sys
import zmq
import os

from phue import Bridge, PhueRegistrationException

if os.name == 'nt':
    from msvcrt import getch, kbhit
else:
    import curses

# Philips Hue bridge IP address
HUE_BRIDGE_IP = '192.168.1.4'

# Hue lamp name
HUE_LAMP = "Demo 1"

# Select Walabot scan arena (minimum, maximum, res)
#           R [cm]     Phi [deg]  Theta [deg]
ARENA = [(20, 80, 1), (-4, 4, 1), (-4, 4, 1)]

# Samples collection window
SAMPLES = 60


class WalaServer(multiprocessing.Process):
    ''' Walabot server class
        Enables detaching between where the Walabot
        collects data and where the data is processed.
    '''

    def __init__(self, arena, ready):
        super(WalaServer, self).__init__()

        self.ready = ready
        self.arena = arena

    def run(self):
        '''Main Walabot capture process'''

        print("Initialize API")
        import WalabotAPI
        WalabotAPI.Init()
        WalabotAPI.Initialize()

        # Check if a Walabot is connected
        try:
            WalabotAPI.ConnectAny()

        except WalabotAPI.WalabotError as err:
            print("Failed to connect to Walabot.\nerror code: " + str(err.code))
            return

        print("Connected to Walabot")
        WalabotAPI.SetProfile(WalabotAPI.PROF_SENSOR_NARROW)

        # Set scan arena
        WalabotAPI.SetArenaR(*self.arena[0])
        WalabotAPI.SetArenaPhi(*self.arena[1])
        WalabotAPI.SetArenaTheta(*self.arena[2])
        print("Arena set")

        # Set image filter
        WalabotAPI.SetDynamicImageFilter(WalabotAPI.FILTER_TYPE_DERIVATIVE)

        # Start scan
        WalabotAPI.Start()
        WalabotAPI.StartCalibration()

        # Start ZMQ server
        context = zmq.Context()
        self.socket = context.socket(zmq.REP)
        self.socket.bind("tcp://*:5556")
        print("Walabot server started")

        # Signal that Walabot server is ready
        self.ready.set()
        capture = True
        message = ''

        # Main loop for getting messages from client
        # and capturing images with the Walabot.
        while capture:
            try:
                message = self.socket.recv_string(flags=zmq.NOBLOCK)

            # Trigger a capture when there is no command
            except zmq.error.Again:
                # Trigger image capture
                WalabotAPI.Trigger()

                # Get energy reading
                energy = WalabotAPI.GetImageEnergy()

            # Client requested server to stop
            if message == 'stop':
                capture = False

            # Client requested Walabot energy reading
            elif message == 'energy':
                self.socket.send_pyobj(energy)

            message = ''

        self.socket.send_string('stopped')

    def stop(self):
        '''Stop capture process and disconnect from Walabot'''
        self.WalabotAPI.Stop()
        self.WalabotAPI.Disconnect()


def breath_loop(stdscr, socket):
    '''Hue control loop'''

    # Set no delay for key-press capture on Linux
    if stdscr is not None:
        stdscr.nodelay(1)

    # Connect to Philips Hue bridge
    try:
        hue_bridge = Bridge(HUE_BRIDGE_IP)
    except PhueRegistrationException:
        # First time connect
        print("Press the 'Philips' button on the bridge and press any key")

        if os.name == 'nt':
            key = ord(getch())
        else:
            key = stdscr.getch()

        hue_bridge = Bridge(HUE_BRIDGE_IP)

    hue_bridge.connect()
    print("Connected to Philips Hue bridge")

    # Make sure lamp is on
    hue_bridge.set_light(HUE_LAMP, 'on', True)

    # Prepare energy log
    energy_log = []

    # Initialize lamp brightness, hue and saturation
    prev_bri = 0
    hue = 43690

    hue_bridge.set_light(HUE_LAMP, 'bri', 150)
    hue_bridge.set_light(HUE_LAMP, 'hue', hue)
    hue_bridge.set_light(HUE_LAMP, 'sat', 250)

    print("Breath...")

    # Make sure there are 5 samples in the energy log
    for i in range(5):
        socket.send_string('energy')
        energy_log.append(socket.recv_pyobj())

    last_peak = time.time()

    active = True
    samples = SAMPLES

    # Lamp control loop
    while active:
        # Capture energy reading from Walabot
        socket.send_string('energy')
        enrg = socket.recv_pyobj()

        # Rolling energy log; Add a sample at the end
        # and remove a sample from the start. Also,
        # make sure there is no overflow.
        if len(energy_log) <= samples:
            energy_log.append(enrg)
        if len(energy_log) == samples + 1:
            energy_log.pop(0)
        if len(energy_log) > samples:
            energy_log = energy_log[-samples:]

        # Average last three samples for a smother response
        enrg = sum(energy_log[-3:]) / 3

        # Get local minimum and maximum energy values
        max_enrg = max(energy_log)
        min_enrg = 0  # min(energy_log)

        # Normalize to lamp brightness levels
        bri = int(195 * ((enrg - min_enrg) / (max_enrg - min_enrg)) + 60)

        # Comment out for debug
#        print("bri = {0}, value = {1}, min = {2}, max = {3}".format(bri, enrg, min_enrg, max_enrg))

        # Capture breath peak time
        if bri > 90:
            last_peak = time.time()

        # Red lamp if last breath peak was more than 13 seconds ago,
        # or if no breathing is detected.
        if time.time() - last_peak > 13 or max_enrg < 0.0002:
            hue = 65000
        else:
            # Shift to red according to last breath peak
            hue = 43690 + 1600 * int(time.time() - last_peak)

        # Prevent hue overflow
        hue = 65000 if hue > 65000 else hue

        # Increase brightness as lamp turns red, regardless
        # of breathing rate.
        bri += int((hue - 43690) / 42)
        bri = 255 if bri > 255 else bri

        # Only send a lamp commands when brightness changes
        if abs(bri - prev_bri) > 2:
            hue_bridge.set_light(HUE_LAMP, 'bri', bri)
            prev_bri = bri

            # To make sure we don't flood bridge with commands
            time.sleep(0.1)
            hue_bridge.set_light(HUE_LAMP, 'hue', hue)
            time.sleep(0.1)

        # Check for key-press
        # Windows
        if os.name == 'nt':
            if kbhit():
                key = ord(getch())
            else:
                key = -1
        # Linux
        else:
            key = stdscr.getch()

        if key != -1:
            # 'q' to quit
            if key == ord('q'):
                active = False

            # 'space' return to default samples window
            if key == 32:
                samples = SAMPLES
                print("Samples = " + str(samples))

            # Check for special keys
            if key == 224:
                # Windows
                if os.name == 'nt':
                    key = ord(getch())
                # Linux
                else:
                    key = stdscr.getch()

                # 'up' key to increase samples window
                if key == 72:
                    samples += 10
                    if samples > 250:
                        samples = 250

                # 'down' key to decrease samples window
                if key == 80:
                    samples -= 10
                    if samples < 10:
                        samples = 10

                print("Samples = " + str(samples))


if __name__ == '__main__':

    # Star Walabot capture server
    ready = multiprocessing.Event()
    wv = WalaServer(ARENA, ready)
    wv.start()

    # Start Walabot client
    print("Starting capture")
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5556")

    # Wait until Walabot configuration is done
    walabot_is_ready = ready.wait(10.0)

    if walabot_is_ready:
        print("Starting breathing monitor")

        # Windows
        if os.name == 'nt':
            breath_loop(None, socket)
        # Linux - run with curses for key-press capture
        else:
            curses.wrapper(breath_loop, socket)

    # Walabot server timeout
    else:
        print("Timed-out on Walabot setup.")
        sys.exit(1)

    # Send server the stop signal
    socket.send_string('stop')
    stopped = socket.recv_string()

    # Wait for server to stop
    if stopped == 'stopped':
        wv.join()
        print("Done!")
    else:
        wv.terminate()
        sys.exit(1)

    sys.exit(0)
