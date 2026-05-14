# bag_bci

ROS nodes for recording experiment data (bag files + parameter snapshots) during BCI-VR sessions.

---

## 1. save_bag.py

Records a `rosbag` with all topics relevant to the active paradigm and modality, plus a YAML snapshot of the full ROS parameter server for exact experiment reproducibility.

Rosbag is stopped via **SIGINT** (not SIGTERM) so the bag file is properly finalized and indexed on shutdown.

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `~subject` | `unknown_subject` | Subject ID used in the output filename |
| `~paradigm` | `hybrid` | Active paradigm: `mi`, `cvsa`, or `hybrid` |
| `~modality` | `evaluation` | Session mode: `calibration` or `evaluation` |
| `~filepath` | `.` | Directory where bag and YAML files are written |
| `~record_audio` | `false` | Also record the `/audio` topic (requires `AudioRecorder.py` running) |

### Output files

```
<filepath>/
  <subject>_<YYYYMMDD_HHMMSS>.bag    ← rosbag with selected topics
  <subject>_<YYYYMMDD_HHMMSS>.yaml   ← full ROS param server dump
```

### Recorded topics

#### Common topics (all paradigms and modalities)

| Topic | Message type | Content |
|-------|-------------|---------|
| `/neurodata` | `rosneuro_msgs/NeuroFrame` | Raw EEG from acquisition |
| `/events/bus` | `rosneuro_msgs/NeuroEvent` | Protocol markers (trial start/end, feedback, etc.) |
| `/artifact_presence` | `artifacts_bci/artifact_presence` | EOG/peak artifact flags + seq |
| `/rosout` | `rosgraph_msgs/Log` | Per-node log output |
| `/rosout_agg` | `rosgraph_msgs/Log` | Aggregated ROS log |

#### Evaluation-only topics — `paradigm:=mi`

| Topic | Content |
|-------|---------|
| `/mi/eeg_fbcsp` | FBCSP variance features (MI channels + CSP) |
| `/mi/neuroprediction/raw` | sLDA raw classifier output |
| `/mi/neuroprediction/integrated/raw` | Buffer integrator output |
| `/mi/neuroprediction/integrated/normalized` | Normalized integrator output |

#### Evaluation-only topics — `paradigm:=cvsa`

| Topic | Content |
|-------|---------|
| `/cvsa/eeg_fbcsp` | FBCSP variance features (CVSA channels + CSP) |
| `/cvsa/neuroprediction/raw` | sLDA raw classifier output |
| `/cvsa/neuroprediction/integrated/raw` | Buffer integrator output |
| `/cvsa/neuroprediction/integrated/normalized` | Normalized integrator output |

#### Evaluation-only topics — `paradigm:=hybrid`

| Topic | Content |
|-------|---------|
| `/mi/eeg_fbcsp` | FBCSP features for MI path |
| `/cvsa/eeg_fbcsp` | FBCSP features for CVSA path |
| `/mi/neuroprediction/raw` | MI classifier output |
| `/cvsa/neuroprediction/raw` | CVSA classifier output |
| `/hybrid/neuroprediction/integrated/raw` | Bayesian-fused integrator output |
| `/hybrid/neuroprediction/integrated/normalized` | Normalized integrator output |

#### Optional

| Topic | Enabled by | Content |
|-------|-----------|---------|
| `/audio` | `record_audio:=true` | Real-time audio chunks from `AudioRecorder.py` |

> **Calibration mode**: only common topics are recorded. The FBCSP and classifier pipeline
> is not active during calibration, so paradigm-specific topics are omitted.

### Usage

The node is launched automatically by `evaluation.launch` and `calibration.launch`:

```bash
roslaunch launchers_bci evaluation.launch  paradigm:=hybrid subject:=S01
roslaunch launchers_bci calibration.launch paradigm:=mi     subject:=S01
```

To run standalone:

```bash
rosrun bag_bci save_bag.py \
    _subject:=S01 \
    _paradigm:=hybrid \
    _modality:=evaluation \
    _filepath:=/home/paolo/bci_vr_ws/recordings/S01/evaluation \
    _record_audio:=false
```

---

## 2. AudioRecorder.py

Captures synchronized audio during experiments.

### Key features

- Records mono audio at 44 112 Hz → `.wav` file
- Publishes audio chunks in real time on `/audio` (includable in the bag via `record_audio:=true`)
- Subscribes to `/events/bus` and logs `NeuroEvent` timestamps relative to recording start
- Warns if a silence stream (all zeros) is detected (microphone diagnostic)
- Thread-safe: separate lock between audio callback and event callback

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `~audio_file` | `./protocol_audio.wav` | Output `.wav` path |
| `~event_markers_file` | `./event_markers.txt` | Event timestamp log path |
| `~event_topic` | `/events/bus` | ROS event topic to time-stamp |

### Usage

```bash
rosrun bag_bci AudioRecorder.py \
    _audio_file:=/path/to/output.wav \
    _event_markers_file:=/path/to/events.txt
```

---

## Dependencies

- **Python**: `rospy`, `pyyaml`, `subprocess`, `signal`, `numpy`, `sounddevice`
- **ROS messages**: `rosneuro_msgs`, `artifacts_bci`
