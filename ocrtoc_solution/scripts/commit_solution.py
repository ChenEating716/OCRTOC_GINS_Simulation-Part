#! /usr/bin/env python
# -*- coding: utf-8 -*-
# 基础包
import rospy
import actionlib
import numpy as np
import time
# 通信接口定义
import ocrtoc_task.msg
from control_msgs.msg import GripperCommandActionGoal
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint
# 自己包使用
import robot_control
import math
import copy

class CommitSolution(object):
    def __init__(self, name):
        # Init action.
        self.action_name = name
        self.action_server = actionlib.SimpleActionServer(
            self.action_name, ocrtoc_task.msg.CleanAction,
            execute_cb=self.execute_callback, auto_start=False)
        self.action_server.start()
        rospy.loginfo(self.action_name + " is running.")

        self.arm_cmd_pub = rospy.Publisher(
            rospy.resolve_name('arm_controller/command'),
            JointTrajectory, queue_size=10)
        self.gripper_cmd_pub = rospy.Publisher(
            rospy.resolve_name('gripper_controller/gripper_cmd/goal'),
            GripperCommandActionGoal, queue_size=10)
        # grasp point
        self.need_to_ignore = ['pan_tefal','bowl_a','bowl','bleach_cleanser','plate']
        self.Need_to_Adjust = {'gelatin_box': [0, 0, 0, 0, math.pi, math.pi/2],
                               'potted_meat_can': [0, 0, 0, 0, math.pi, -math.pi/2],
                               'cracker_box':[0,0,-0.01,0,math.pi,0],
                               'pudding_box':[0,0,-0.007,0,math.pi,0],
                               'sugar_box': [0,0,-0.01,0,math.pi,0],
                               'mustard_bottle': [0, 0, 0.01, 0, math.pi , math.pi/2],
                               'bleach_cleanser': [0, 0, 0.015, 0, math.pi , math.pi/2],
                               'power_drill':[-0.01, 0, 0, 0, math.pi , math.pi/2],
                               'extra_large_clamp':[-0.002, -0.002, 0, 0, math.pi , 3*math.pi/4],
                               'hammer':[0, 0, -0.01, 0, math.pi , 0],
                               'pan_tefal':[0, -0.02, 0, 0, math.pi , 0],
                               'bowl':[0, -0.02, 0, 0, math.pi , 0],
                               'bowl_a':[0, -0.01, 0, 0, math.pi , 0],
                               'spoon':[0, 0, -0.005, 0, math.pi , 0],
                               'fork':[0, 0, -0.005, 0, math.pi , 0],
                               'knife':[0, 0, -0.005, 0, math.pi , 0],
                               'phillips_screwdriver':[0, 0, -0.005, 0, math.pi , 0],
                               'jenga': [0,0,-0.01,0,math.pi,0],
                               'e_cups':[0.005,0,0,0,math.pi,0],
                               'f_cups':[0.005,0,0,0,math.pi,0],
                               'g_cups':[0.005,0,0,0,math.pi,0],
                               'h_cups':[0,0.007,0,0,math.pi,0]}
        # see more in test_grasp.py

        # create messages that are used to publish feedback/result.
        self.feedback = ocrtoc_task.msg.CleanFeedback()
        self.result = ocrtoc_task.msg.CleanResult()

        # get models directory.
        materials_path = rospy.get_param('~materials_dir',
                                         '/root/ocrtoc_materials')
        self.models_dir = materials_path + '/models'
        rospy.loginfo("Models dir: " + self.models_dir)

    def process_goal_pose(self, goal_object_list, goal_pose_list):
        """
	    改变了原先的读取位置的方法，用字典代替列表
        """
        return_pose_list = []
        for pose in goal_pose_list:
            return_pose_list.append(np.array(
                [pose.position.x, pose.position.y, pose.position.z, pose.orientation.x, pose.orientation.y,
                 pose.orientation.z, pose.orientation.w]))
        goal_list = dict(zip(goal_object_list, return_pose_list))
        return goal_list
    
    def process_grasp_pose(self, name_list, objpose_list):
        grasp_list = dict(zip(name_list, objpose_list))
        n = len(name_list)
        for i in range(0,n):
            for j in range(0,n-i-1):
                if ((grasp_list.get(name_list[j])[1])**2 + (grasp_list.get(name_list[j])[0])**2)<((grasp_list.get(name_list[j+1])[1])**2 + (grasp_list.get(name_list[j+1])[0])**2):
                    name_list[j],name_list[j+1]=name_list[j+1],name_list[j]
        
        for obj in self.need_to_ignore:
            if obj in name_list:
                name_list.remove(obj)

        return name_list, grasp_list



    def execute_callback(self, goal):
        rospy.loginfo("Get clean task.")
        goal_object_list = goal.object_list
        goal_pose_list = goal.pose_list
        goal_pose_list = self.process_goal_pose(goal_object_list, goal_pose_list)

        #导入场景
        rospy.loginfo("Load models")
        for object_name in goal.object_list:
            object_model_dir = self.models_dir + '/' + object_name
            rospy.loginfo("Object model dir: " + object_model_dir)
        rospy.sleep(1.0)

        #获取目标场景中位置
        robot = robot_control.Robot()
        objects = robot_control.Objects(get_pose_from_gazebo=False)
        name_list=None
        objname_list = None
        print(name_list)
        print(objname_list)
        while not rospy.is_shutdown():
            print("Ready to Picking")
            robot.getpose_home(1)
            objects.get_pose()
            robot.home(t=1)
            if objects.names is not None :
                name_list = copy.deepcopy(objects.names)
                objname_list = copy.deepcopy(objects.x)
                name_list,grasp_list = self.process_grasp_pose(objects.names, objects.x)
                print(name_list)
                print(grasp_list)
            for i in name_list:
                # 1:获取物体名称和物体目标位置
                name = i
                goal_pose = goal_pose_list.get(name)

                # 2:抓取物体并运动到目标位置
                #print("Traget is {},it's Pose is {}".format(objects.names[i], origin_pose))
                if name in self.Need_to_Adjust:
                    param = self.Need_to_Adjust.get(name)
                    grasp_pose = robot.get_pickpose_from_pose(grasp_list.get(name),x=param[0],y=param[1],z=param[2],
                                                              degreeR=param[3], degreeP=param[4], degreeY=param[5])
                else:
                    grasp_pose = robot.get_pickpose_from_pose(grasp_list.get(name))
                robot.gripper_control(angle=0, force=1)
                robot.move_updown(grasp_pose, grasp=True, fast_vel=0.4, slow_vel=0.1)
                #robot.home()
                # 运动到目标位置并放下
                if name in self.Need_to_Adjust:
                    try:
                        param = self.Need_to_Adjust.get(name)
                        place_pose = robot.get_pickpose_from_pose(goal_pose, x=param[0], y=param[1], z=param[2],
                                                                  degreeR=param[3], degreeP=param[4], degreeY=param[5])
                    except:
                        print("DenseFusion Don't detect {}".format(name))
                        continue
                else:
                    try:
                        place_pose = robot.get_pickpose_from_pose(goal_pose)
                    except:
                        print("DenseFusion Don't detect {}".format(name))
                        continue
                # 只是用xyz,旋转角度使用grasp的角度
                # 改变了运动轨迹，去掉了多余的gethome，提高了上方点位置
                robot.move_updown(place_pose, grasp=False, fast_vel=0.4, slow_vel=0.1)
                robot.getpose_home()
            break

        # Example: set status "Aborted" and quit.
        if self.action_server.is_preempt_requested():
            self.result.status = "Aborted"
            self.action_server.set_aborted(self.result)
            return

        # Example: send feedback.
        self.feedback.text = "write_feedback_text_here"
        self.action_server.publish_feedback(self.feedback)
        rospy.loginfo("Pub feedback")
        rospy.sleep(1.0)

        # Example: set status "Finished" and quit.
        self.result.status = "Finished"
        rospy.loginfo("Done.")
        self.action_server.set_succeeded(self.result)
        ##### User code example ends #####


if __name__ == '__main__':
    rospy.init_node('commit_solution')
    commit_solution = CommitSolution('commit_solution')
    rospy.spin()


