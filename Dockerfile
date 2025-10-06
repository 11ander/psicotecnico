FROM ros:noetic

ENV DEBIAN_FRONTEND=noninteractive

# Paquetes base
RUN apt-get update && apt-get install -y --no-install-recommends \
    rviz \
    ros-noetic-moveit \
    curl \
    apt-utils \
    python3-pip \
    python-is-python3 \
    ssh \
    net-tools \
    sudo \
    iputils-ping \
    nmap \
    xauth \
    ros-noetic-robot-state-publisher \
    ros-noetic-joint-state-publisher \
    git \
    ros-noetic-usb-cam \
    htop \
    libxmlrpc-core-c3-dev \
    # dependencias útiles para OpenCV con GUI
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python
RUN pip install --no-cache-dir \
    catkin_tools \
    tensorboard \
    opencv-python

# Crear usuario no root con UID/GID 1000 para encajar con el host
RUN groupadd -g 1000 robotica_tiago && \
    useradd -ms /bin/bash -u 1000 -g 1000 robotica_tiago && \
    echo "robotica_tiago ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Grupos típicos para acceso a /dev/dri, /dev/tty*, etc.
RUN usermod -aG video,dialout,plugdev robotica_tiago

# Preparar entorno del usuario
RUN mkdir -p /home/robotica_tiago/carpeta_compartida && \
    chown -R robotica_tiago:robotica_tiago /home/robotica_tiago

# Sourcing del setup propio (si existe) al iniciar bash
RUN echo 'if [ -f /home/robotica_tiago/carpeta_compartida/setup_env.sh ]; then source /home/robotica_tiago/carpeta_compartida/setup_env.sh; fi' >> /home/robotica_tiago/.bashrc

USER robotica_tiago
WORKDIR /home/robotica_tiago

ENTRYPOINT ["sleep", "infinity"]
