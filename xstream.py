#!/usr/bin/python3
# -*- Mode: Python; indent-tabs-mode: t; c-basic-offset: 4; tab-width: 4 -*-
#
## \file xstream.py
## \brief Webcam to IceCast2 streaming software.
#
# xstream.py
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

debug = 0

## Debugging:
## GST_DEBUG=3,python:5,gnl*:5 ./xstream.py > debug.log 2>&1


## Debug
#import pdb
#pdb.set_trace()


import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gst', '1.0')
gi.require_version('GstVideo', '1.0')
from gi.repository import GObject, Gtk, GdkPixbuf, Gdk

# Needed for window.get_xid(), xvimagesink.set_window_handle(), respectively:
# for window.get_xid()
from gi.repository import GdkX11
# for sink.set_window_handle()
from gi.repository import GstVideo

from gi.repository import Gst

import os
import sys
import time
import v4l2_devices
from xstreamconfig import XstreamConfig


config_file = 'settings.ini'
cfg = XstreamConfig(config_file)

# Input devices
video_device = cfg.getConf('video_device')
# Video parameters
video_size = cfg.getConf('video_size')
framerate = cfg.getConf('framerate')
video_quality = cfg.getConf('video_quality')
# Audio parameters
audio_quality = cfg.getConf('audio_quality')
audio_channels = cfg.getConf('audio_channels')
audio_rate = cfg.getConf('audio_rate')
# Icecast server
ic_server = cfg.getConf('ic_server')
ic_port = cfg.getConf('ic_port')
ic_mountpoint = cfg.getConf('ic_mountpoint')
# Icecast password for user source
ic_password = cfg.getConf('ic_password')
# Icecast Metadata
ic_metadata_name = cfg.getConf('ic_metadata_name')
ic_metadata_description = cfg.getConf('ic_metadata_description')
ic_metadata_genre = cfg.getConf('ic_metadata_genre')
ic_metadata_url = cfg.getConf('ic_metadata_url')

# Glade interface xml
UI_FILE = "xstream.ui"


# This is very important!
GObject.threads_init()
Gst.init(None)


"""
gst-launch-1.0
  v4l2src device=/dev/video0 ! queue ! videoconvert !
    videorate ! video/x-raw,framerate=25/2 !
    videoscale ! video/x-raw,width=320,height=240 ! tee name=tscreen ! queue !
    autovideosink tscreen. ! queue !
    theoraenc quality=16 ! queue ! oggmux name=mux
  pulsesrc ! audio/x-raw,rate=22050,channels=2 ! queue ! audioconvert !
    vorbisenc quality=0.2 ! queue ! mux. mux. ! queue ! tee name=tfile ! queue !
  filesink location=stream-test.ogg tfile. ! queue !
  shout2send ip=HOSTNAME port=8000 mount=stream.ogg password=PASSWORD
    streamname=StreamName description= genre= url=http://www.example.com/
"""


class VideoStream(Gst.Bin):
    """ Video input, output to local display (DrawingArea) with autovideosink.
    Encode video input with theora codec.

    # v4l2src device=/dev/video0
    #  ! queue ! videoconvert
    #  ! videorate ! video/x-raw,framerate=25/2
    #  ! videoscale ! video/x-raw,width=320,height=240
    #  ! tee name=tscreen
    #  ! queue ! autovideosink tscreen. ! queue
    #  ! theoraenc quality=16 ! queue !
    """
    def __init__(self, video_size, framerate, video_quality):
        super().__init__()

        # video_sizes (320x240): sizes[0], sizes[1]
        self.video_size = video_size
        self.video_sizes = self.video_size.split("x")
        self.framerate = framerate
        self.video_quality = video_quality
        print (' * VideoStream video size:      {0}'.format(self.video_size))
        print (' * VideoStream framerate:       {0}'.format(self.framerate))
        print (' * VideoStream theora quality:  {0}'.format(self.video_quality))

        # Create elements: Video
        self.queue_v0 = Gst.ElementFactory.make('queue', None)
        self.videoconvert0 = Gst.ElementFactory.make('videoconvert', None)
        self.videorate0 = Gst.ElementFactory.make('videorate', None)
        self.videoscale0 = Gst.ElementFactory.make('videoscale', None)
        self.tee_screen = Gst.ElementFactory.make('tee', 'teeScreen')
        self.queue_tscreen1 = Gst.ElementFactory.make('queue', None)
        self.queue_tscreen2 = Gst.ElementFactory.make('queue', None)
        ## 0:00:00.212733634 ^[[331m22518^[[00m      0x215a640 ^[[33;01mWARN   ^
        #[[00m ^[[00m             v4l2src gstv4l2src.c:593:gst_v4l2src_query:
        #<v4l2src0>^[[00m Can't give latency since framerate isn't fixated !
        #self.xvimagesink0 = Gst.ElementFactory.make('xvimagesink', None)
        self.xvimagesink0 = Gst.ElementFactory.make('autovideosink', None)
        self.enc = Gst.ElementFactory.make('theoraenc', None)
        self.queue_v1 = Gst.ElementFactory.make('queue', None)

        capsfilter1 = Gst.caps_from_string(
            'video/x-raw, width=%s, height=%s, framerate=%s' %
            (self.video_sizes[0], self.video_sizes[1], self.framerate))

        # Add elements to Bin: Video
        self.add(self.queue_v0)
        self.add(self.videoconvert0)
        self.add(self.videorate0)
        self.add(self.videoscale0)
        self.add(self.tee_screen)
        self.add(self.queue_tscreen1)
        self.add(self.queue_tscreen2)
        self.add(self.xvimagesink0)
        self.add(self.enc)
        self.add(self.queue_v1)

        # Set properties          # lanczos, highest quality scaling
        self.videoscale0.set_property('method', 3)
        self.xvimagesink0.set_property('sync', 'false')
        self.enc.set_property('quality', int(self.video_quality))

        # Link elements: Video    # capsfilter: Scale to 320x240
        self.queue_v0.link(self.videoconvert0)
        self.videoconvert0.link(self.videorate0)
        self.videorate0.link(self.videoscale0)
        self.videoscale0.link_filtered(self.tee_screen, capsfilter1)
        self.tee_screen.link(self.queue_tscreen1)
        self.tee_screen.link(self.queue_tscreen2)
        self.queue_tscreen1.link(self.xvimagesink0)
        self.queue_tscreen2.link(self.enc)
        self.enc.link(self.queue_v1)

        # Add Ghost Pads
        self.add_pad(Gst.GhostPad.new(
            'sink', self.queue_v0.get_static_pad('sink')))
        self.add_pad(Gst.GhostPad.new(
            'src', self.queue_v1.get_static_pad('src')))


class AudioStream(Gst.Bin):
    """ Audio input.
    Audio encoder, encode with vorbis codec.
    """
    def __init__(self, audio_quality):
        super().__init__()

        self.audio_quality = audio_quality
        print (' * AudioStream audio quality:   {0}'.format(self.audio_quality))

        # Create elements: Audio
        self.queue_a0 = Gst.ElementFactory.make('queue', None)
        self.audioconvert0 = Gst.ElementFactory.make('audioconvert', None)
        self.enc_audio = Gst.ElementFactory.make('vorbisenc', None)
        self.queue_a1 = Gst.ElementFactory.make('queue', None)

        # Add elements to Bin: Audio
        self.add(self.queue_a0)
        self.add(self.audioconvert0)
        self.add(self.enc_audio)
        self.add(self.queue_a1)

        # Set properties
        self.enc_audio.set_property('quality', float(self.audio_quality))

        # Link elements: Audio
        self.queue_a0.link(self.audioconvert0)
        self.audioconvert0.link(self.enc_audio)
        self.enc_audio.link(self.queue_a1)

        # Add Ghost Pads
        self.add_pad(Gst.GhostPad.new(
            'sink', self.queue_a0.get_static_pad('sink')))
        self.add_pad(Gst.GhostPad.new(
            'src', self.queue_a1.get_static_pad('src')))


# XStreamGUI class
class XStreamGUI:
    """ Main XStreamGUI class.
    """

    def on_window_destroy(self, object, data=None):
        """ Quit main window with cancel """
        print("quit with cancel")
        ## (xstream.py:4981): GStreamer-CRITICAL **:
        ## Trying to dispose element pipeline0, but it is in PLAYING instead of
        ## the NULL state.
        ## You need to explicitly set elements to the NULL state before
        ## dropping the final reference, to allow them to clean up.
        ## This problem may also be caused by a refcounting bug in the
        ## application or some element.
        self.pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()

    def on_gtk_quit_activate(self, menuitem, data=None):
        """ Quit main window, menu "File -> Quit" """
        print("quit from menu")
        self.pipeline.set_state(Gst.State.NULL)
        Gtk.main_quit()

    def on_gtk_about_activate(self, menuitem, data=None):
        """ Open about dialog, menu "Help -> About" """
        print("help about selected")
        ## Run dialog About
        self.response = self.aboutdialog.run()
        self.aboutdialog.hide()

    def on_gtk_preferences_activate(self, menuitem, data=None):
        """ Open Preferences window, menu "Edit -> Preferences" """
        print("edit preferences selected")
        ## Run dialog Preferences
        self.response = self.dialog_prefs.run()
        self.dialog_prefs.hide()

    def on_notebook1_switch_page():
        print('Notebook1 switch page')

    def device_connected(observer, device):
        print('{0!r} added'.format(device))

    """
    values:      framerate = ['25:1', '25:2', '25:3', '25:4', '25:5', '10:1']
    index_value: '25:2'
    return:      1
    """
    def get_enumvalue_index(self, values, index_value):
        self.values = values
        self.index_value = index_value
        for index, value in enumerate(self.values):
            if value == index_value:
                #print (index)
                break
        return index

    def __init__(self):
        """ The constructor. """

        ## GTK Builder
        self.builder = Gtk.Builder()
        self.builder.add_from_file(UI_FILE)
        self.builder.connect_signals(self)

        window = self.builder.get_object('window')

        #---- Themes
        # Get the default window background color for the the current theme.
        win_style_context = window.get_style_context()
        bg = win_style_context.lookup_color('theme_bg_color')[1].to_string()
        # Then we set that as the background for GtkToolbar
        # We also make the boarder transparent
        css_provider = Gtk.CssProvider()
        toolbar_css = ".inline-toolbar.toolbar { background: %s; \
        border-color: transparent; }" % (bg)
        css_provider.load_from_data(toolbar_css.encode('UTF-8'))
        screen = Gdk.Screen.get_default()
        win_style_context.add_provider_for_screen(screen, css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        ## Dialog About
        self.aboutdialog = self.builder.get_object("aboutdialog1")
        ## Dialog Preferences
        self.dialog_prefs = self.builder.get_object("dialog_prefs")
        ## Button for start and stop streaming
        self.button_start_stop_stream = self.builder.get_object(
            "button_start_stop_stream")
        ## Label: Camera status
        self.label_camera_status = self.builder.get_object(
            'label_camera_status')
        self.vbox_video = self.builder.get_object('vbox_video')
        ## DrawingArea: Webcam preview area
        self.drawingarea_movie1 = self.builder.get_object('drawingarea_movie1')
        self.entry_s_name = self.builder.get_object('entry_s_name')
        self.entry_s_description = self.builder.get_object(
            'entry_s_description')
        self.entry_s_genre = self.builder.get_object('entry_s_genre')
        self.entry_s_url = self.builder.get_object('entry_s_url')
        self.label_info_dumpfile = self.builder.get_object(
            'label_info_dumpfile')
        self.label_info_video_device = self.builder.get_object(
            'label_info_video_device')
        self.label_info_video_size = self.builder.get_object(
            'label_info_video_size')
        self.label_info_framerate = self.builder.get_object(
            'label_info_framerate')
        self.label_info_video_quality = self.builder.get_object(
            'label_info_video_quality')
        self.label_info_audio_quality = self.builder.get_object(
            'label_info_audio_quality')
        self.label_info_audio_channels = self.builder.get_object(
            'label_info_audio_channels')
        self.label_info_audio_rate = self.builder.get_object(
            'label_info_audio_rate')
        self.statusbar = self.builder.get_object('statusbar')

        #---- Dialog Preferences -----------------------------------------------
        self.entry_ic_server1 = self.builder.get_object('entry_ic_server1')
        self.entry_ic_port1 = self.builder.get_object('entry_ic_port1')
        self.entry_ic_password1 = self.builder.get_object('entry_ic_password1')
        self.entry_ic_metadata_name1 = self.builder.get_object(
            'entry_ic_metadata_name1')
        self.entry_ic_metadata_description1 = self.builder.get_object(
            'entry_ic_metadata_description1')
        self.entry_ic_metadata_genre1 = self.builder.get_object(
            'entry_ic_metadata_genre1')
        self.entry_ic_metadata_url1 = self.builder.get_object(
            'entry_ic_metadata_url1')
        self.comboboxtext_video_device1 = self.builder.get_object(
            'comboboxtext_video_device1')
        self.comboboxtext_video_size1 = self.builder.get_object(
            'comboboxtext_video_size1')
        self.comboboxtext_framerate1 = self.builder.get_object(
            'comboboxtext_framerate1')
        self.comboboxtext_video_quality1 = self.builder.get_object(
            'comboboxtext_video_quality1')
        self.comboboxtext_audio_quality1 = self.builder.get_object(
            'comboboxtext_audio_quality1')
        self.comboboxtext_audio_channels1 = self.builder.get_object(
            'comboboxtext_audio_channels1')
        self.comboboxtext_audio_rate1 = self.builder.get_object(
            'comboboxtext_audio_rate1')
        self.entry_ic_server1.set_text(cfg.getConf('ic_server'))
        self.entry_ic_port1.set_text(cfg.getConf('ic_port'))
        self.entry_ic_password1.set_text(cfg.getConf('ic_password'))
        self.entry_ic_metadata_name1.set_text(cfg.getConf('ic_metadata_name'))
        self.entry_ic_metadata_description1.set_text(cfg.getConf(
            'ic_metadata_description'))
        self.entry_ic_metadata_genre1.set_text(cfg.getConf('ic_metadata_genre'))
        self.entry_ic_metadata_url1.set_text(cfg.getConf('ic_metadata_url'))

        # Input devices # ['/dev/video0', '/dev/video1', 'auto']
        self.video_device = v4l2_devices.list_devices()
        # autovideosrc
        self.video_device.append('auto')
        for val in self.video_device:
            self.comboboxtext_video_device1.append_text(val)
        self.comboboxtext_video_device1.set_active(self.get_enumvalue_index(
            self.video_device, cfg.getConf('video_device')))

        # Video parameters
        framerate = ['25:1', '25:2', '25:3', '25:4', '25:5', '10:1']
        for val in framerate:
            self.comboboxtext_framerate1.append_text(val)
        self.comboboxtext_framerate1.set_active(self.get_enumvalue_index(
            framerate, cfg.getConf('framerate')))

        # Video quality (0 - 63)
        vquality_num = 0
        v_quality = []
        while (vquality_num <= 63):
            self.comboboxtext_video_quality1.append_text(str(vquality_num))
            # mora biti string
            v_quality.append(str(vquality_num))
            vquality_num += 1

        self.comboboxtext_video_quality1.set_active(self.get_enumvalue_index(
            v_quality, cfg.getConf('video_quality')))

        if debug == 1:
            print ('')
            print ('DEBUG:  v_quality:     %s' % v_quality)
            print ('DEBUG:  video_quality: %s' % video_quality)
            print ('DEBUG:  index:         %s' % self.get_enumvalue_index)
            #(v_quality, cfg.getConf('video_quality')))
            print ('')

        self.video_size = ['160x128', '320x240', '360x288', '640x480',
            '720x576']
        for val in self.video_size:
            self.comboboxtext_video_size1.append_text(val)
        self.comboboxtext_video_size1.set_active(self.get_enumvalue_index(
            self.video_size, cfg.getConf('video_size')))
        # Video parameters.

        # Audio parameters
        audio_quality = ['-0.1', '0', '0.1', '0.2', '0.3', '0.4', '0.5', '0.6',
            '0.7', '0.8', '0.9', '1.0']
        for val in audio_quality:
            self.comboboxtext_audio_quality1.append_text(val)
        self.comboboxtext_audio_quality1.set_active(self.get_enumvalue_index(
            audio_quality, cfg.getConf('audio_quality')))

        # Audio channels
        audio_channels = ['1', '2']
        for val in audio_channels:
            self.comboboxtext_audio_channels1.append_text(val)
        self.comboboxtext_audio_channels1.set_active(self.get_enumvalue_index(
            audio_channels, cfg.getConf('audio_channels')))

        # Audio rate
        audio_rate = ['11025', '22050', '44100', '48000']
        for val in audio_rate:
            self.comboboxtext_audio_rate1.append_text(val)
        self.comboboxtext_audio_rate1.set_active(self.get_enumvalue_index(
            audio_rate, cfg.getConf('audio_rate')))

        self.button_preferences_save = self.builder.get_object(
            "button_preferences_save")
        self.button_preferences_save.connect("clicked", self.preferences_save)
        #---- Dialog Preferences. ----------------------------------------------

        self.button_start_stop_stream.connect("clicked", self.start_stop)
        self.vbox_video.override_background_color(
            Gtk.StateType.NORMAL, Gdk.RGBA(.5, .5, .5, .5))

        ## Streaming state: preparing or running
        self.sstate = 'preparing'
        self.label_camera_status.set_markup("Camera started... Ready to stream")
        self.label_camera_status.override_background_color(
            Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 255, 1))
        self.statusbar.push(1, "Camera started... Ready to stream")

        ## Create GStreamer pipeline
        self.pipeline = Gst.Pipeline()

        window.show_all()

        # You need to get the XID after window.show_all().  You shouldn't get it
        # in the on_sync_message() handler because threading issues will cause
        # segfaults there.
        self.xid = self.drawingarea_movie1.get_property('window').get_xid()
        # Stop stream, just play in local window
        self.stop_stream()

    def stop_stream(self):
        #print ("XID: %s" % self.xid)
        """ Stop stream... Just play in local window. """
        self.button_start_stop_stream.get_child().set_from_file(
                "media/video-camera-icon-64x64-black_blue.png")
        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline = Gst.Pipeline()
        self.video_device = cfg.getConf('video_device')
        self.video_size = cfg.getConf('video_size')
        self.framerate = cfg.getConf('framerate')
        self.framerate = self.framerate.replace(':', '/')
        self.video_quality = cfg.getConf('video_quality')
        self.label_info_video_device.set_text(self.video_device)
        self.label_info_video_size.set_text(self.video_size)
        self.label_info_framerate.set_text(self.framerate)
        self.label_info_video_quality.set_text(self.video_quality)
        self.label_info_audio_quality.set_text('')
        self.label_info_audio_channels.set_text('')
        self.label_info_audio_rate.set_text('')
        print ("{0:<20s} {1:1s}".format(' * Video device:', self.video_device))

        # Create elements
        if self.video_device == 'auto':
            self.v4l2src0 = Gst.ElementFactory.make('autovideosrc', None)
        else:
            self.v4l2src0 = Gst.ElementFactory.make('v4l2src', None)
        self.video = VideoStream(
            self.video_size, self.framerate, self.video_quality)

        # Add elements to pipeline
        self.pipeline.add(self.v4l2src0)
        self.pipeline.add(self.video)

        # Set properties
        if self.video_device != "auto":
            self.v4l2src0.set_property("device", self.video_device)

        # Link elements
        self.v4l2src0.link(self.video)

        ## Create bus to get events from GStreamer pipeline
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        # This is needed to make the video output in our DrawingArea:
        self.bus.enable_sync_message_emission()
        self.bus.connect("message", self.on_message)
        self.bus.connect('sync-message::element', self.on_sync_message)
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop_cam(self):
        """ Stop playing, set state NULL """
        self.button_start_stop_stream.set_label("Start Stream")
        self.pipeline.set_state(Gst.State.NULL)

    def start_stop(self, w):
        #print ("XID: %s" % self.xid)
        self.video_device = cfg.getConf('video_device')
        self.video_size = cfg.getConf('video_size')
        self.framerate = cfg.getConf('framerate')
        self.framerate = framerate.replace(':', '/')
        self.video_quality = cfg.getConf('video_quality')
        self.audio_quality = cfg.getConf('audio_quality')
        self.audio_channels = cfg.getConf('audio_channels')
        self.audio_rate = cfg.getConf('audio_rate')
        self.ic_server = cfg.getConf('ic_server')
        self.ic_port = cfg.getConf('ic_port')
        self.ic_mountpoint = cfg.getConf('ic_mountpoint')
        self.ic_password = cfg.getConf('ic_password')
        self.ic_metadata_name = cfg.getConf('ic_metadata_name')
        self.ic_metadata_description = cfg.getConf('ic_metadata_description')
        self.ic_metadata_genre = cfg.getConf('ic_metadata_genre')
        self.ic_metadata_url = cfg.getConf('ic_metadata_url')

        """ Start/stop streaming to Icecast server """
        if self.sstate == 'preparing':
            self.time_stream_started_f = time.strftime("%Y%m%d%H%M%S")
            self.button_start_stop_stream.get_child().set_from_file(
                "media/video-camera-icon-64x64-black_green.png")
            self.pipeline.set_state(Gst.State.NULL)
            self.pipeline = Gst.Pipeline()

            # Recording
            self.out_dir = 'data'
            if not os.path.exists(self.out_dir):
                os.makedirs(self.out_dir)
            self.dumpfile = self.out_dir + '/stream-' \
            + self.time_stream_started_f + '.ogv'

            # Info
            self.label_info_dumpfile.set_text(self.dumpfile)
            self.label_info_video_device.set_text(self.video_device)
            self.label_info_video_size.set_text(self.video_size)
            self.label_info_framerate.set_text(self.framerate)
            self.label_info_video_quality.set_text(self.video_quality)
            self.label_info_audio_quality.set_text(self.audio_quality)
            self.label_info_audio_channels.set_text(self.audio_channels)
            self.label_info_audio_rate.set_text(self.audio_rate)
            self.video_sizes = self.video_size.split("x")
            print ("{0:<20s} {1:1s}".format(
                ' * Video device:', self.video_device))
            print ("{0:<20s} {1:1s}".format(' * Dumping to:', self.dumpfile))
            print ("{0:<20s} {1:1s}".format(' * HTTP Stream:', 'http://'
            + self.ic_server + ':' + self.ic_port + '/' + self.ic_mountpoint))

            #---- Audio/Video --------------------------------------------------

            # Create elements
            # Video
            if self.video_device == 'auto':
                self.v4l2src0 = Gst.ElementFactory.make('autovideosrc', None)
            else:
                self.v4l2src0 = Gst.ElementFactory.make('v4l2src', None)
            self.video = VideoStream(
                self.video_size, self.framerate, self.video_quality)
            self.muxogg = Gst.ElementFactory.make('oggmux', 'muxOgg')
            # Audio
            self.pulsesrc0 = Gst.ElementFactory.make('pulsesrc', None)
            self.audio = AudioStream(self.audio_quality)
            self.queue_audio_mux = Gst.ElementFactory.make('queue', None)
            self.tfile = Gst.ElementFactory.make('tee', 'tfile')
            self.queue_tfile_0 = Gst.ElementFactory.make('queue', None)
            self.queue_tfile_1 = Gst.ElementFactory.make('queue', None)
            self.filesink = Gst.ElementFactory.make('filesink', None)
            self.shout2send0 = Gst.ElementFactory.make('shout2send', None)
            self.capsfilter2 = Gst.caps_from_string('audio/x-raw, rate='
            + self.audio_rate + ', channels=' + self.audio_channels)

            # Set properties # device=/dev/video0
            if self.video_device != "auto":
                self.v4l2src0.set_property("device", self.video_device)
            self.filesink.set_property('location', self.dumpfile)
            self.shout2send0.set_property("ip", self.ic_server)
            self.shout2send0.set_property("port", int(self.ic_port))
            self.shout2send0.set_property("mount", self.ic_mountpoint)
            self.shout2send0.set_property("password", self.ic_password)
            self.shout2send0.set_property("streamname", self.ic_metadata_name)
            self.shout2send0.set_property(
                "description", self.ic_metadata_description)
            self.shout2send0.set_property("genre", self.ic_metadata_genre)
            self.shout2send0.set_property("url", self.ic_metadata_url)

            # Add elements to pipeline
            self.pipeline.add(self.v4l2src0)
            self.pipeline.add(self.video)
            self.pipeline.add(self.muxogg)
            self.pipeline.add(self.pulsesrc0)
            self.pipeline.add(self.audio)
            self.pipeline.add(self.queue_audio_mux)
            self.pipeline.add(self.tfile)
            self.pipeline.add(self.queue_tfile_0)
            self.pipeline.add(self.queue_tfile_1)
            self.pipeline.add(self.filesink)
            self.pipeline.add(self.shout2send0)

            # Link Elements
            self.v4l2src0.link(self.video)
            self.video.link(self.muxogg)
            self.pulsesrc0.link_filtered(self.audio, self.capsfilter2)
            self.audio.link(self.muxogg)
            self.muxogg.link(self.queue_audio_mux)
            self.queue_audio_mux.link(self.tfile)
            # TeeFile -> filesink
            self.tfile.link(self.queue_tfile_0)
            self.queue_tfile_0.link(self.filesink)
            # TeeFile -> shout2send
            self.tfile.link(self.queue_tfile_1)
            self.queue_tfile_1.link(self.shout2send0)

            #---- Audio/Video. -------------------------------------------------

            # Create bus to get events from GStreamer pipeline
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            # This is needed to make the video output in our DrawingArea
            self.bus.enable_sync_message_emission()
            self.bus.connect("message", self.on_message)
            self.bus.connect('sync-message::element', self.on_sync_message)

            # Play & Dump2File & Stream 2 IceCast2 server
            self.pipeline.set_state(Gst.State.PLAYING)
            self.f = float(framerate.split(':')[0] + '.0') / float(
                framerate.split(':')[1] + '.0')
            self.label_camera_status.set_markup(
                "Streaming at " + framerate + " frames per second")
            self.label_camera_status.override_background_color(
                Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 100, 0, 0.9))
            #self.statusbar.pop(1)
            self.statusbar.push(1, "Streaming at " + str(self.f) +
            " frames per second")
            self.sstate = 'running'
        else:
            self.stop_stream()
            self.label_camera_status.set_markup(
                "Camera started... Ready to stream")
            self.label_camera_status.override_background_color(
                Gtk.StateFlags.NORMAL, Gdk.RGBA(0, 0, 255, 1))
            #self.statusbar.pop(1)
            self.statusbar.push(1, "Camera started... Ready to stream")
            self.sstate = 'preparing'

    def on_pad_added(self, element, pad):
        string = pad.query_caps(None).to_string()
        print('on_pad_added():', string)
        if string.startswith('audio/'):
            pad.link(self.audio.get_static_pad('sink'))
        elif string.startswith('video/'):
            pad.link(self.video.get_static_pad('sink'))

    def on_message(self, bus, message):
        """ On Message do some action: stop_cam, stop_stream.
        """
        if message.type == Gst.MessageType.ERROR:
            if self.sstate == 'preparing':
                self.label_camera_status.set_markup(
                    "Error initializing camera... Check your devices")
                self.label_camera_status.override_background_color(
                    Gtk.StateFlags.NORMAL, Gdk.RGBA(255, 0, 0, 1))
                self.stop_cam()
                self.button_start_stop_stream.get_child().set_from_file(
                "media/video-camera-icon-64x64.png")
            if self.sstate == 'running':
                self.label_camera_status.set_markup(
                    "Error starting stream... Check your parameters")
                self.label_camera_status.override_background_color(
                    Gtk.StateFlags.NORMAL, Gdk.RGBA(255, 0, 0, 1))
                self.stop_stream()
                self.sstate = 'preparing'
                self.button_start_stop_stream.get_child().set_from_file(
                "media/video-camera-icon-64x64.png")
            err, debug = message.parse_error()
            print("Error: %s" % err, debug)

    def on_sync_message(self, bus, msg):
        """ Set window property. """
        if msg.get_structure().get_name() == 'prepare-window-handle':
            print('prepare-window-handle')
            msg.src.set_property('force-aspect-ratio', True)
            msg.src.set_window_handle(self.xid)

    def on_error(self, bus, msg):
        """ On Error, print error. """
        print('on_error():', msg.parse_error())

    def preferences_save(self, w):
        """ Preferences window, menu "Edit -> Preferences"    Button [Save]
        """
        cfg.setConf('ic_server', self.entry_ic_server1.get_text())
        cfg.setConf('ic_port', self.entry_ic_port1.get_text())
        cfg.setConf('ic_password', self.entry_ic_password1.get_text())
        cfg.setConf('ic_metadata_name', self.entry_ic_metadata_name1.get_text())
        cfg.setConf('ic_metadata_description',
        self.entry_ic_metadata_description1.get_text())
        cfg.setConf('ic_metadata_genre',
        self.entry_ic_metadata_genre1.get_text())
        cfg.setConf('ic_metadata_url', self.entry_ic_metadata_url1.get_text())
        cfg.setConf('video_device',
            self.comboboxtext_video_device1.get_active_text())
        cfg.setConf('framerate', self.comboboxtext_framerate1.get_active_text())
        cfg.setConf('video_size',
            self.comboboxtext_video_size1.get_active_text())
        cfg.setConf('video_quality',
            self.comboboxtext_video_quality1.get_active_text())
        cfg.setConf('audio_quality',
            self.comboboxtext_audio_quality1.get_active_text())
        cfg.setConf('audio_channels',
            self.comboboxtext_audio_channels1.get_active_text())
        cfg.setConf('audio_rate',
            self.comboboxtext_audio_rate1.get_active_text())
        # Save config file
        cfg.saveConf(config_file)
        print("preferences saved")


def main():
    """ Main function """
    app = XStreamGUI()
    Gtk.main()

if __name__ == "__main__":
    sys.exit(main())

