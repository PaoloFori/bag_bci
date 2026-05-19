#!/usr/bin/env python3

import os
import signal
import threading
import time
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

        subject          = rospy.get_param('~subject',          'unknown_subject')
        filepath         = rospy.get_param('~filepath',         '.')
        paradigm         = rospy.get_param('~paradigm',         'hybrid')
        modality         = rospy.get_param('~modality',         'evaluation')
        record_audio     = rospy.get_param('~record_audio',     False)
        # How long to wait after startup before snapshotting the parameter
        # server.  All nodes are normally up within the first few seconds.
        param_dump_delay = rospy.get_param('~param_dump_delay', 5.0)

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

        # param_file uses the same timestamp as the bag so they are paired.
        # The actual dump is deferred to stop() so that ALL nodes have had
        # time to push their parameters onto the ROS parameter server.
        self._param_file = os.path.join(filepath, f"{subject}_{date_string}.yaml")

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
        rospy.loginfo(f"[SaveBag] Param file: {self._param_file} (saved ~{param_dump_delay}s after start)")

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

        # 3. Schedule the parameter dump.
        # Strategy (in priority order):
        #   a) Delayed thread: fires `param_dump_delay` seconds after startup,
        #      when all nodes have loaded their parameters.
        #   b) on_shutdown hook: fires when roslaunch sends SIGINT, while the
        #      ROS master is still reachable (better than the finally block).
        #   c) stop() fallback: last-chance attempt in the finally block.
        # rosparam dump (subprocess) is used instead of rospy.get_param because
        # the CLI tool is more resilient at the edges of the node lifecycle.
        self._params_dumped = threading.Event()
        rospy.on_shutdown(self._on_shutdown_dump)
        t = threading.Thread(target=self._delayed_dump,
                             args=(param_dump_delay,), daemon=True)
        t.start()

    # ── Helpers ──────────────────────────────────────────────────────────
    def _dump_params(self, label=''):
        """Snapshot the full ROS parameter server via `rosparam dump`.

        Using the CLI subprocess is more reliable than rospy.get_param('/')
        at the edges of the node lifecycle (startup / shutdown races).
        """
        if self._params_dumped.is_set():
            return   # already saved — skip
        tag = f" [{label}]" if label else ''
        try:
            result = subprocess.run(
                ['rosparam', 'dump', self._param_file, '/'],
                timeout=8,
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                rospy.loginfo(f"[SaveBag]{tag} Parameters saved to {self._param_file}")
                self._params_dumped.set()
            else:
                rospy.logerr(f"[SaveBag]{tag} rosparam dump failed: {result.stderr.strip()}")
        except Exception as e:
            rospy.logerr(f"[SaveBag]{tag} Failed to save parameters: {e}")

    def _delayed_dump(self, delay):
        """Sleep `delay` seconds then dump — called from a daemon thread."""
        time.sleep(delay)
        self._dump_params(label=f'+{delay}s')

    def _on_shutdown_dump(self):
        """rospy.on_shutdown hook — fires while the master is still alive."""
        self._dump_params(label='on_shutdown')

    # ── Shutdown ─────────────────────────────────────────────────────────
    def stop(self):
        # Stop rosbag first so it can flush and index the file.
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

        # Fallback: if the session ended before the delayed dump fired,
        # try a last-chance dump now.  The ROS master may already be going
        # down, so we accept failure silently.
        if hasattr(self, '_params_dumped') and not self._params_dumped.is_set():
            rospy.logwarn("[SaveBag] Delayed dump did not fire — attempting fallback dump.")
            self._dump_params()



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
