"""
Serial Arduino Controller.

Sends fall information to the Arduino over USB serial using the protocol:
FALL:<angle>:<x>:<y>\\n

Uses a threaded queue so the CV pipeline never blocks on serial writes.
"""

import serial
import threading
import queue
import time
import logging

logger = logging.getLogger(__name__)

class ArduinoController:
    def __init__(self, port: str = "COM3", baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.serial_conn = None
        self.queue = queue.Queue()
        self.running = False
        self.thread = None
        self.connected = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        if self.serial_conn:
            self.serial_conn.close()

    def send_fall_event(self, angle: float, x: int, y: int):
        """Enqueue a FALL command for the Arduino."""
        cmd = f"FALL:{int(angle)}:{int(x)}:{int(y)}\n"
        self.queue.put(cmd)

    def _run_loop(self):
        # Attempt to connect
        try:
            self.serial_conn = serial.Serial(self.port, self.baudrate, timeout=1)
            time.sleep(2) # Wait for Arduino reset
            self.connected = True
            logger.info(f"Connected to Arduino on {self.port}")
        except serial.SerialException as e:
            logger.error(f"Failed to connect to Arduino on {self.port}: {e}")
            self.connected = False
            # We still run the loop to empty the queue so it doesn't block the system
        
        while self.running:
            try:
                cmd = self.queue.get(timeout=0.5)
                if self.connected and self.serial_conn:
                    try:
                        self.serial_conn.write(cmd.encode('utf-8'))
                        logger.info(f"Arduino <- {cmd.strip()}")
                    except serial.SerialException as e:
                        logger.error(f"Arduino write error: {e}")
                        self.connected = False
            except queue.Empty:
                pass
