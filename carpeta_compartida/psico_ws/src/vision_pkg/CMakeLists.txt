cmake_minimum_required(VERSION 3.0.2)
project(vision_pkg)

find_package(catkin REQUIRED COMPONENTS
  rospy
  std_msgs
  actionlib
  actionlib_msgs
  pal_interaction_msgs
)

add_action_files(
  DIRECTORY action
  FILES Vision.action
)

generate_messages(
  DEPENDENCIES
  std_msgs
  actionlib_msgs
)

catkin_package(
  CATKIN_DEPENDS rospy std_msgs actionlib actionlib_msgs pal_interaction_msgs
)

catkin_install_python(
  PROGRAMS
    src/vision_pkg/servidor_vision.py
    src/vision_pkg/test_vision_client.py
    src/vision_pkg/checkpoint_follower_api.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
