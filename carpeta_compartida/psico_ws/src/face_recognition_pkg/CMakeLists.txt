cmake_minimum_required(VERSION 3.0.2)
project(face_recognition_pkg)

## Primero: encontrar catkin (define los macros)
find_package(catkin REQUIRED COMPONENTS
  roscpp
  rospy
  std_msgs
  sensor_msgs
  actionlib
  actionlib_msgs
  message_generation
)

## Ahora sí: habilitar instalación Python vía setup.py
catkin_python_setup()

## === Acciones ===
add_action_files(
  DIRECTORY action
  FILES FaceRecognition.action
)

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

## Instalar scripts para rosrun
catkin_install_python(PROGRAMS
  src/face_recognition_pkg/recognize_action_server.py
  src/face_recognition_pkg/cliente_action_face.py
  src/face_recognition_pkg/recognize_ros.py  # opcional
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)
