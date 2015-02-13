#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: t; c-basic-offset: 4; tab-width: 4 -*-
#
## \file xstreamconfig.py
## \brief Webcam to IceCast2 streaming software.
#
# xstreamconfig.py
# Copyright (C) 2014 Matej Fabijanic <root4unix@gmail.com>
#
# xstream is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# xstream is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

# Debug
#import pdb
#pdb.set_trace()


import configparser
import os

config = configparser.ConfigParser()
section = 'main'


def createConfig(self, path):
    """
    Create a config file
    """
    try:
        config.add_section(section)
    except:
        pass
    # Input Device
    config.set(section, 'video_device', '/dev/video0')
    # Video
    config.set(section, 'video_size', '320x240')
    config.set(section, 'framerate', '25:2')
    config.set(section, 'video_quality', '16')
    # Audio
    config.set(section, 'audio_quality', '1.0')
    config.set(section, 'audio_channels', '1')
    config.set(section, 'audio_rate', '22050')
    # Icecast 2
    config.set(section, 'ic_server', '127.0.0.1')
    config.set(section, 'ic_port', '8000')
    config.set(section, 'ic_mountpoint', 'stream-test.ogv')
    config.set(section, 'ic_password', 'hackme')
    # Icecast Metadata
    config.set(section, 'ic_metadata_name', 'NAME')
    config.set(section, 'ic_metadata_description', 'DESCRIPTION')
    config.set(section, 'ic_metadata_genre', 'GENRE')
    config.set(section, 'ic_metadata_url', 'http://www.example.com/')

    with open(path, "w") as config_file:
        config.write(config_file)


class XstreamConfig():

    def __init__(self, path):
        config.read(path)
        if not os.path.exists(path):
            createConfig(self, path)

    def getConf(self, key):
        return config.get(section, key)

    def setConf(self, key, value):
        config.set(section, key, value)

    def saveConf(self, path):
        # write changes back to the config file
        with open(path, "w") as config_file:
            config.write(config_file)

