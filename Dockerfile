FROM ros:noetic

RUN apt update && apt install -y rviz \
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
         sudo \
         libxmlrpc-core-c3-dev

RUN pip install catkin_tools \
                tensorboard \
                opencv-python

RUN rm -rf /var/lib/apt/lists/* && \
    groupadd -g 1000 robotica_tiago && \
    useradd -ms /bin/bash robotica_tiago -u 1000 -g 1000 && \
    echo "robotica_tiago ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers && \
    echo "source /home/robotica_tiago/carpeta_compartida/setup_env.sh" >> /home/robotica_tiago/.bashrc && \
    RUN echo 'robotica_tiago:robotica_tiago' | chpasswd && \
    chown robotica_tiago:robotica_tiago /home/robotica_tiago && \
    mkdir -p /var/run/robotica_tiago/1000 && \
    chown robotica_tiago:robotica_tiago /var/run/robotica_tiago/1000

USER robotica_tiago

ENTRYPOINT [ "sleep", "infinity"]