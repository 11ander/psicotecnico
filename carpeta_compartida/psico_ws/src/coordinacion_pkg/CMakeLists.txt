cmake_minimum_required(VERSION 3.0.2)
project(coordinacion_pkg)

find_package(catkin REQUIRED COMPONENTS
  roscpp
  rospy
  std_msgs
  sensor_msgs
  actionlib
  actionlib_msgs
  message_generation
)

## === Acciones ===
add_action_files(
  DIRECTORY action
  FILES MobilityExam.action
)

## === Mensajes/Servicios (si los hubiese) ===
# add_message_files(FILES ...)
# add_service_files(FILES ...)

## === Generación de mensajes SIEMPRE antes de catkin_package ===
generate_messages(
  DEPENDENCIES
  std_msgs
  actionlib_msgs
)

catkin_package(
  CATKIN_DEPENDS
    rospy
    std_msgs
    sensor_msgs
    actionlib
    actionlib_msgs
    message_runtime
)

include_directories(${catkin_INCLUDE_DIRS})

## Instalar scripts para rosrun (usa carpeta scripts/)
catkin_install_python(PROGRAMS
  src/coordinacion_pkg/mobility_exam_action_server.py
  src/coordinacion_pkg/cliente_action_mobility.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)