#!/usr/bin/env python3

import os
import rospy
import yaml
import subprocess
from time import gmtime, strftime

class SaveBag:
    def __init__(self):
        rospy.init_node('save_bag', anonymous=True)
        
        # Parameters
        subject = rospy.get_param('~subject', 'unknown_subject')
        filepath = rospy.get_param('~filepath', '.')
        paradigm = rospy.get_param('~paradigm', 'hybrid')
        
        date_string = strftime("%Y%m%d_%H%M%S", gmtime())
        
        bag_file = os.path.join(filepath, f"{subject}_{date_string}.bag")
        param_file = os.path.join(filepath, f"{subject}_{date_string}.yaml")
        
        topics_list = [
            "/events/bus", 
            "/artifact_presence", 
            f"/{paradigm}/neuroprediction/integrated/normalized", 
            f"/{paradigm}/neuroprediction/integrated/raw",        
            "/mi/neuroprediction/raw",
            "/cvsa/neuroprediction/raw",                   
            "/eeg_power", 
            "/integrator/parameter_descriptions",
            "/integrator/parameter_updates", 
            "/neurodata", 
            "/rosout", 
            "/vr/status/ready"
        ]
        
        topics_string = " ".join(topics_list)
        
        # 1. Salva i parametri su file YAML
        try:
            params = rospy.get_param('/')
            with open(param_file, 'w') as f:
                yaml.dump(params, f, default_flow_style=False)
            rospy.loginfo(f"Parametri salvati correttamente.")
        except Exception as e:
            rospy.logerr(f"Errore salvataggio parametri: {e}")

        # 2. Avvia la registrazione
        record_command = f"rosbag record -O {bag_file} {topics_string}"
        rospy.loginfo(f"Registrazione avviata per il paradigma: {paradigm}")
        self.process = subprocess.Popen(record_command, shell=True)

if __name__ == '__main__':
    try:
        sb = SaveBag()
        rospy.spin()
    except rospy.ROSInterruptException:
        if hasattr(sb, 'process'):
            sb.process.terminate()