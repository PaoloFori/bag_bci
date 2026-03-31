# Audio and Data Recording Suite

This repository contains Python-based ROS nodes designed for synchronized audio capture, event logging, and system telemetry recording.

---

## 1. AudioRecorder.py
The `AudioRecorderNode` is responsible for capturing high-quality audio and synchronizing it with system events.

### Key Features
* **Real-time Recording**: Captures mono audio at 44112 Hz and saves it directly to a `.wav` file.
* **ROS Integration**: Publishes audio chunks as `AudioMessage` on the `/audio` topic for other nodes to process in real-time.
* **Event Synchronization**: Subscribes to the `/events/bus` topic and logs `NeuroEvent` markers with timestamps relative to the start of the recording.
* **Silence Detection**: Includes a diagnostic feature that monitors input data and logs a warning if a continuous stream of zeros (silence) is detected, suggesting microphone issues.
* **Thread Safety**: Uses a threading lock to prevent conflicts between the audio callback (writing frames) and the event callback (logging markers).

---

## 2. save_bag.py
The `SaveBag` node automates the process of recording ROS bag files and archiving system parameters.

### Key Features
* **Parameter Backup**: Automatically exports all current ROS parameters to a `.yaml` file before starting the recording to ensure experimental reproducibility.
* **Selective Recording**: Executes a `rosbag record` command for a specific list of critical topics, including EEG data (`/neurodata`), event buses, and paradigm-specific predictions.
* **Dynamic Naming**: Generates filenames using a combination of the subject ID, current date, and time to prevent overwriting data.
* **Paradigm Support**: Dynamically adjusts topic paths based on the `paradigm` parameter (e.g., "hybrid").

---

## Installation & Requirements

### Dependencies
Ensure you have the following installed:
* **Python Libraries**: `numpy`, `sounddevice`, `pyyaml`.
* **ROS Messages**: `rosneuro_msgs` and `feedback_cvsa`.

### Usage

#### Launching the Audio Recorder:
```bash
python3 AudioRecorder.py _audio_file:="path/to/output.wav" _event_markers_file:="path/to/events.txt"
```

#### Launching the Data Saver:
```bash
python3 save_bag.py _subject:="Subject01" _paradigm:="hybrid" _filepath:="./data"
```
