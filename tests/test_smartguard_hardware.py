"""
Unit tests for Arduino Controller serial protocol.
"""

import pytest
from smartguard.hardware.arduino_controller import ArduinoController


def test_arduino_command_formatting():
    # Instantiate without connecting to a real serial port
    controller = ArduinoController(port="TEST_PORT", baudrate=9600)

    # Queue a fall event command
    controller.send_fall_event(angle=42.6, x=150, y=380)

    # Inspect the item in the queue
    cmd = controller.queue.get_nowait()
    assert cmd == "FALL:42:150:380\n"


def test_arduino_command_rounding():
    controller = ArduinoController(port="TEST_PORT", baudrate=9600)
    controller.send_fall_event(angle=89.9, x=639.4, y=479.8)

    cmd = controller.queue.get_nowait()
    assert cmd == "FALL:89:639:479\n"
