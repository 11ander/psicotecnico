cmake_minimum_required(VERSION 3.0.2)
project(web_server_pkg)

## Encuentra catkin y las dependencias de ROS que usas desde Python
find_package(catkin REQUIRED COMPONENTS
  rospy
  actionlib
  geometry_msgs
  move_base_msgs
  tf
  pal_interaction_msgs
  rpi_pkg
  audicion_pkg
  coordinacion_pkg
  face_recognition_pkg
)

## <<< AÑADIR ESTA LÍNEA >>>
catkin_python_setup()

###################################
## catkin specific configuration ##
###################################
catkin_package(
  CATKIN_DEPENDS
    rospy
    actionlib
    geometry_msgs
    move_base_msgs
    tf
    pal_interaction_msgs
    rpi_pkg
    audicion_pkg
    coordinacion_pkg
    face_recognition_pkg
)

###########
## Build ##
###########

include_directories(
  ${catkin_INCLUDE_DIRS}
)

#############
## Install ##
#############

# Scripts Python que se lanzan como nodos:
# - app.py  -> servidor Flask + puente ROS
# - set_initial_pose.py -> script de inicialización de pose
catkin_install_python(
  PROGRAMS
    src/web_server_pkg/app.py
    src/web_server_pkg/set_initial_pose.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

# Ficheros de recursos para Flask (plantillas, estáticos, datos)
install(
  DIRECTORY
    src/web_server_pkg/templates
    src/web_server_pkg/static
    src/web_server_pkg/data
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
  USE_SOURCE_PERMISSIONS
)

# (Opcional) instala los archivos de launch
install(
  DIRECTORY launch
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}
)
