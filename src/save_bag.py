#!/usr/bin/env python3

import os
import signal
import rospy
import yaml
import subprocess
from time import gmtime, strftime


class SaveBag:

    # Topics always recorded regardless of paradigm or modality
    COMMON_TOPICS = [
        "/neurodata",
        "/events/bus",
        "/artifact_presence",
        "/rosout",
        "/rosout_agg",
    ]

    # Additional topics recorded only in evaluation mode (classifier pipeline active)
    EVALUATION_TOPICS = {
        "mi": [
            "/mi/eeg_fbcsp",
            "/mi/neuroprediction/raw",
            "/mi/neuroprediction/integrated/raw",
            "/mi/neuroprediction/integrated/normalized",
        ],
        "cvsa": [
            "/cvsa/eeg_fbcsp",
            "/cvsa/neuroprediction/raw",
            "/cvsa/neuroprediction/integrated/raw",
            "/cvsa/neuroprediction/integrated/normalized",
        ],
        "hybrid": [
            "/mi/eeg_fbcsp",
            "/cvsa/eeg_fbcsp",
            "/mi/neuroprediction/raw",
            "/cvsa/neuroprediction/raw",
            "/hybrid/neuroprediction/integrated/raw",
            "/hybrid/neuroprediction/integrated/normalized",
        ],
    }

    def __init__(self):
        rospy.init_node('save_bag', anonymous=True)

        subject       = rospy.get_param('~subject',       'unknown_subject')
        filepath      = rospy.get_param('~filepath',      '.')
        paradigm      = rospy.get_param('~paradigm',      'hybrid')
        modality      = rospy.get_param('~modality',      'evaluation')
        record_audio  = rospy.get_param('~record_audio',  False)

        if paradigm not in self.EVALUATION_TOPICS:
            rospy.logerr(f"[SaveBag] Unknown paradigm '{paradigm}'. "
                         f"Valid: {list(self.EVALUATION_TOPICS.keys())}")
            return

        if modality not in ('calibration', 'evaluation'):
            rospy.logerr(f"[SaveBag] Unknown modality '{modality}'. "
                         f"Valid: calibration, evaluation")
            return

        os.makedirs(filepath, exist_ok=True)

        date_string = strftime("%Y%m%d_%H%M%S", gmtime())
        bag_file    = os.path.join(filepath, f"{subject}_{date_string}.bag")
        param_file  = os.path.join(filepath, f"{subject}_{date_string}.yaml")

        # Build topic list
        topics = list(self.COMMON_TOPICS)
        if modality == 'evaluation':
            topics += self.EVALUATION_TOPICS[paradigm]
        if record_audio:
            topics.append("/audio")

        rospy.loginfo(f"[SaveBag] Modality  : {modality}")
        rospy.loginfo(f"[SaveBag] Paradigm  : {paradigm}")
        rospy.loginfo(f"[SaveBag] Bag file  : {bag_file}")
        rospy.loginfo(f"[SaveBag] Audio     : {record_audio}")
        rospy.loginfo(f"[SaveBag] Topics    : {topics}")

        # 1. Save all ROS parameters to YAML for exact reproducibility
        try:
            params = rospy.get_param('/')
            with open(param_file, 'w') as f:
                yaml.dump(params, f, default_flow_style=False)
            rospy.loginfo(f"[SaveBag] Parameters saved to {param_file}")
        except Exception as e:
            rospy.logerr(f"[SaveBag] Failed to save parameters: {e}")

        # 2. Start rosbag recording
        # Use a process group so we can send SIGINT to the entire group,
        # which lets rosbag finalize and index the bag file properly.
        topics_str     = " ".join(topics)
        record_command = f"rosbag record -O {bag_file} {topics_str}"
        self.process   = subprocess.Popen(
            record_command,
            shell=True,
            preexec_fn=os.setsid,   # new process group for clean SIGINT delivery
        )
        rospy.loginfo("[SaveBag] Recording started.")

    def stop(self):
        if hasattr(self, 'process') and self.process.poll() is None:
            try:
                # SIGINT lets rosbag flush and write the bag index properly;
                # SIGTERM would leave the file truncated/unindexed.
                os.killpg(os.getpgid(self.process.pid), signal.SIGINT)
                self.process.wait(timeout=5)
            except Exception as e:
                rospy.logwarn(f"[SaveBag] Error stopping recording: {e}")
                self.process.kill()
            rospy.loginfo("[SaveBag] Recording stopped.")


if __name__ == '__main__':
    sb = None
    try:
        sb = SaveBag()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass
    finally:
        if sb is not None:
            sb.stop()
