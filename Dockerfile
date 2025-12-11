FROM ros:noetic

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

# ------------------------------------------------------------------
# 1) Paquetes de sistema y ROS adicionales
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Herramientas base
    curl \
    apt-utils \
    python3-pip \
    python-is-python3 \
    ssh \
    sudo \
    net-tools \
    iputils-ping \
    nmap \
    git \
    htop \
    ca-certificates \
    dirmngr \
    gnupg2 \
    build-essential \
    python3-dev \
    # ROS visualización / navegación / cámaras
    rviz \
    ros-noetic-moveit \
    ros-noetic-robot-state-publisher \
    ros-noetic-joint-state-publisher \
    ros-noetic-usb-cam \
    # Dependencias para OpenCV con GUI
    libgl1 \
    libglib2.0-0 \
    libxmlrpc-core-c3-dev \
    # Stack de escritorio remoto vía VNC (que instalaste a mano)
    xvfb \
    x11vnc \
    fluxbox \
    novnc \
    # X11
    xauth \
    ros-noetic-web-video-server \
    ros-noetic-move-base-msgs \
    ros-noetic-map-server \
    ros-noetic-teleop-twist-keyboard \
    && rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# 2) Paquetes de Python del proyecto
#    Usamos el requirements_docker.txt que generaste con pip freeze
# ------------------------------------------------------------------




# ------------------------------------------------------------------
# 3) Usuario no root alineado con el host (UID/GID 1000)
# ------------------------------------------------------------------
RUN groupadd -g 1000 robotica_tiago && \
    useradd -ms /bin/bash -u 1000 -g 1000 robotica_tiago && \
    echo "robotica_tiago ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    usermod -aG video,dialout,plugdev robotica_tiago

# Carpetas del usuario
RUN mkdir -p /home/robotica_tiago/carpeta_compartida && \
    chown -R robotica_tiago:robotica_tiago /home/robotica_tiago

USER robotica_tiago
WORKDIR /home/robotica_tiago



# ------------------------------------------------------------------
# 4) Entorno de ROS y entorno propio al abrir bash
# ------------------------------------------------------------------

# Siempre que abras una shell dentro del contenedor:
# - se hace source del setup de ROS
# - si existe /home/robotica_tiago/carpeta_compartida/setup_env.sh también se hace source
RUN echo 'source /opt/ros/noetic/setup.bash' >> /home/robotica_tiago/.bashrc && \
    echo 'if [ -f /home/robotica_tiago/carpeta_compartida/setup_env.sh ]; then' >> /home/robotica_tiago/.bashrc && \
    echo '  source /home/robotica_tiago/carpeta_compartida/setup_env.sh' >> /home/robotica_tiago/.bashrc && \
    echo 'fi' >> /home/robotica_tiago/.bashrc

# ------------------------------------------------------------------
# 5) Entrada por defecto
# ------------------------------------------------------------------
# Dejamos el contenedor "vivo" para que puedas entrar con docker exec
ENTRYPOINT ["sleep", "infinity"]
