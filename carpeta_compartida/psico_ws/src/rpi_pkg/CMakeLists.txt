cmake_minimum_required(VERSION 3.0.2)
project(rpi_pkg)

## Opcional: habilitar C++11 si usas código C++
# add_compile_options(-std=c++11)

## Encontrar paquetes catkin requeridos
find_package(catkin REQUIRED COMPONENTS
  roscpp
  rospy
  std_msgs
  actionlib
  actionlib_msgs
  message_generation
)

## =============================================
## DECLARACIÓN DE ACCIONES
## =============================================
add_action_files(
  DIRECTORY action
  FILES Reflejos.action
)

## =============================================
## GENERACIÓN DE MENSAJES Y ACCIONES
## =============================================
generate_messages(
  DEPENDENCIES
  std_msgs
  actionlib_msgs
)

## =============================================
## EXPORTACIÓN DEL PAQUETE (para otros paquetes)
## =============================================
catkin_package(
  CATKIN_DEPENDS
    roscpp
    rospy
    std_msgs
    actionlib
    actionlib_msgs
    message_runtime
)

## =============================================
## DIRECTORIOS DE INCLUSIÓN
## =============================================
include_directories(
  ${catkin_INCLUDE_DIRS}
)

## =============================================
## INSTALACIÓN DE SCRIPTS PYTHON
## =============================================
catkin_install_python(PROGRAMS
  src/rpi_pkg/servidor_reflejos.py
  src/rpi_pkg/estado_pulsador.py
  # scripts/cliente_reflejos.py   # descomenta si lo usas
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)