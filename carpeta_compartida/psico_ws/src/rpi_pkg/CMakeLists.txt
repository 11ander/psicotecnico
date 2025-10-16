cmake_minimum_required(VERSION 3.0.2)
project(rpi_pkg)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  rospy
  std_msgs
  actionlib
  actionlib_msgs
  message_generation
)

catkin_python_setup()

add_action_files(
  DIRECTORY action
  FILES
    Reflejos.action
    Memoria.action
)


generate_messages(
  DEPENDENCIES
  std_msgs
  actionlib_msgs
)

catkin_package(
  CATKIN_DEPENDS
    roscpp
    rospy
    std_msgs
    actionlib
    actionlib_msgs
    message_runtime
)

include_directories(${catkin_INCLUDE_DIRS})

catkin_install_python(PROGRAMS
  src/rpi_pkg/servidor_reflejos.py
  src/rpi_pkg/servidor_memoria.py
  src/rpi_pkg/estado_pulsador.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
