#!/usr/bin/env python3

import os
import rospy
from time import gmtime, strftime
import yaml
import rosparam

class save_bag:
    def __init__(self):
        rospy.init_node('save_bag', anonymous=True)
        subject = rospy.get_param('~subject')
        filepath = rospy.get_param('~filepath')
        
        date_string = strftime("%Y%m%d_%H%M%S", gmtime())
        
        bag_file = filepath + '/' + subject + '_' + date_string + '.bag'
        
        topics = "/cvsa/eye /events/bus /cvsa/trials_keep /imu_cvsa /cvsa/neuroprediction /cvsa/features /cvsa/neuroprediction/integrated /cvsa/neuroprediction/raw /cvsa/neuroprediction/icnic /cvsa/artifact_presence"
        record_command = f'rosbag record -O {bag_file} {topics}'
        
        # to save parameters used
        param_file = filepath + '/' + subject + '_' + date_string + '.yaml'
        params = rosparam.get_param('/')
        with open(param_file, 'w') as file:
            yaml.dump(params, file, default_flow_style=False)
        
        # to save the bag file
        os.popen(record_command)
        
if __name__ == '__main__':
    try:
        save_bag()
        rospy.spin()
    except rospy.ROSInterruptException:
        pass