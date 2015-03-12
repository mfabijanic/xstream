# xstream

Main Page
=========


Webcam streaming to Icecast server.




Run xstream:

$ python3 xstream.py




Dependencies
============


* Python3:    https://www.python.org/download/releases/3.0/
* Gstreamer:  http://gstreamer.freedesktop.org/
* v4l-utils




## Webcam preview in local window ##

$ gst-launch-1.0 v4l2src device=/dev/video0 ! queue ! autovideosink




## Webcam preview in local window, stream to server and dump to local file ##

$ gst-launch-1.0
v4l2src device=/dev/video0 ! queue ! videoconvert ! videorate ! video/x-raw,framerate=25/2 ! videoscale ! video/x-raw,width=320,height=240 !
tee name=tscreen ! queue ! autovideosink tscreen. ! queue ! theoraenc quality=16 ! queue !
oggmux name=mux pulsesrc ! audio/x-raw,rate=22050,channels=2 ! queue ! audioconvert ! vorbisenc quality=0.2 ! queue ! mux. mux. ! queue ! tee name=tfile ! queue !
filesink location=stream-test.ogg tfile. ! queue !
shout2send ip=HOSTNAME port=8000 mount=stream.ogg password=PASSWORD streamname=StreamName description=  genre= url=http://www.example.com/




## Webcamera ##


$ sudo apt-get install v4l-utils


Disable autofocus:

$ v4l2-ctl -d 0 -c focus_auto=0


Set focus:

$ v4l2-ctl -d 0 -c focus_absolute=250
