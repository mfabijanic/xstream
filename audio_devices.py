#!/usr/bin/python3

import pyudev


def list_devices():
    list_devices = []
    context = pyudev.Context()

    for device in context.list_devices(subsystem='sound'):
        if device.device_node is not None:
            list_devices.append(device.device_node)

    return list_devices
