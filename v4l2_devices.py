#!/usr/bin/python3

import pyudev
#from pyudev import Context, Device
#import syslog


def list_devices():
    """ List video4linux devices """
    list_devices = []
    context = pyudev.Context()
    #context.log_priority = syslog.LOG_DEBUG

    for device in context.list_devices(subsystem='video4linux'):
        if device.device_node is not None:
            list_devices.append(device.device_node)

    return list_devices

