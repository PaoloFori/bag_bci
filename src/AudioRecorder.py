#!/usr/bin/env python3

import threading
import time
import wave

import numpy as np
import rospy
import sounddevice as sd
from rosneuro_msgs.msg import NeuroEvent
from feedback_cvsa.msg import AudioMessage
from std_msgs.msg import Int16MultiArray
import  datetime 

# Parameters
SAMPLE_RATE = 44112  # Hz
CHUNK_SIZE = 2757 # 16 Hz publish rate
CHANNELS = 1         # Mono recording

DATETIME = datetime.datetime.now().strftime('%Y%m%d.%H%M%S')

AUDIO_FILE = "./protocol_audio.wav"  # Output audio file
EVENT_MARKERS_FILE = "./event_markers.txt"  # File to log event markers

import rospy

class ROSNode:
    def __init__(self,name):
        self.name = name
        rospy.init_node(self.name)

    def loginfo(self, msg):
        rospy.loginfo(f'[{self.name}]  {msg}')
    
    def logwarn(self, msg):
        rospy.logwarn(f'[{self.name}]  {msg}')
    
    def logerr(self, msg):
        rospy.logerr(f'[{self.name}]  {msg}')

    def logdebug(self, msg):
        rospy.logdebug(f'[{self.name}]  {msg}')

class AudioRecorderNode(ROSNode):
    def __init__(self,name='audio_recorder'):

        # Initialize ROS node
        super().__init__(name)

        self.loginfo("Node Initialized")

        # ROS params
        self.audio_file_path = rospy.get_param('~audio_file', AUDIO_FILE)
        self.event_markers_path = rospy.get_param('~event_markers_file', EVENT_MARKERS_FILE)

        # Audio file setup
        self.audio_file = wave.open(self.audio_file_path, 'wb')
        self.audio_file.setnchannels(CHANNELS)
        self.audio_file.setsampwidth(2)  # 16-bit audio
        self.audio_file.setframerate(SAMPLE_RATE)

        # Event markers list
        self.event_markers = []

        # Lock for thread safety
        self.lock = threading.Lock()

        # Audio stream
        self.audio_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            blocksize=CHUNK_SIZE,
            channels=CHANNELS,
            dtype='int16',
            callback=self.audio_callback
        )


        self.first_stamp = None
        # Setup the publisher for the audio stream
        self.pub = rospy.Publisher('/audio', AudioMessage, queue_size=10)

        # Subscribe to the event bus
        self.event_topic = rospy.get_param('~event_topic', '/events/bus')
        self.sub = rospy.Subscriber(self.event_topic, NeuroEvent, self.event_callback)
        self.last_warn = 0

        rospy.sleep(2); # Wait for the other nodes to initialize

        # Flag for stopping the recording
        self.running = True

    def audio_callback(self, indata, frames, time, status):
        if status:
            self.logerr(f"Audio stream error: {status}")

        # Publish audio stream
        msg = AudioMessage()
        msg.header.stamp = self.now()-self.first_stamp #time elapsed since the start of the recording
        msg.header.frame_id = 'audio'
        msg.sample_rate = SAMPLE_RATE
        msg.channels = CHANNELS
        msg.chunk_size = CHUNK_SIZE
        msg.bitdepth = 16
        msg.audio = Int16MultiArray()
        msg.audio.data = indata.flatten().tolist()
        self.pub.publish(msg)

        if sum(indata.flatten()) == 0:    
            if self.last_warn%32 == 0:
                self.logwarn("Silence detected! Check your microphone!!")
                self.last_warn = 1
            else:
                self.last_warn += 1
        else:
            self.last_warn = 0
        # Write audio to the file
        with self.lock:
            self.audio_file.writeframes(indata.tobytes())

    def event_callback(self, msg):
        event_time = self.now()-self.first_stamp

        self.loginfo(f"Received event: {msg.event} at {event_time}")
        with self.lock:
            self.event_markers.append((event_time, msg.event))


    def run(self):
        try:
            rospy.loginfo("Audio recording is starting")
            self.audio_stream.start()
            rospy.spin()
        except rospy.ROSInterruptException:
            self.sub.shutdown()
            pass
        finally:
            rospy.loginfo("Stopping audio recording...")
            with self.lock:
                self.audio_stream.close()
                self.audio_file.close()

        self.loginfo(f"Audio recording saved to {self.audio_file_path}")
        self.loginfo(f"Event markers saved to {self.event_markers_path}")


    def now(self):
        stamp = rospy.Time.now()
        if self.first_stamp is None:
            self.first_stamp = stamp
        return stamp

if __name__ == "__main__":
    node = AudioRecorderNode()
    node.run()
