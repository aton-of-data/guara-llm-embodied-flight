# Guará development image: ROS 2 Humble + PX4 v1.17.0 SITL (SIH, headless) + Micro XRCE-DDS Agent.
# Versions must match third_party/VERSIONS.md. Sources: GROUNDING.md A.17-A.21.
FROM ros:humble-ros-base-jammy

ARG PX4_REF=v1.17.0
ARG PX4_COMMIT=d6f12ad1c4f70ad3230afd7d86e971421e02fef4
ARG XRCE_AGENT_REF=v2.4.3

ENV DEBIAN_FRONTEND=noninteractive \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    TZ=UTC \
    RUNS_IN_DOCKER=true

RUN apt-get update -y --quiet \
 && apt-get install -y --quiet --no-install-recommends sudo git lsb-release python3-pip \
    ros-humble-eigen3-cmake-module libeigen3-dev ros-humble-ament-cmake-gtest \
 && rm -rf /var/lib/apt/lists/*

# PX4 at the pinned commit, with submodules (third_party/ clone is shallow without submodules).
RUN git -c advice.detachedHead=false clone --quiet --depth 1 --branch ${PX4_REF} \
      --recurse-submodules --shallow-submodules \
      https://github.com/PX4/PX4-Autopilot.git /opt/PX4-Autopilot \
 && test "$(git -C /opt/PX4-Autopilot rev-parse HEAD)" = "${PX4_COMMIT}"

# PX4 dependencies without NuttX toolchain and without simulator GUIs.
RUN bash /opt/PX4-Autopilot/Tools/setup/ubuntu.sh --no-nuttx --no-sim-tools \
 && rm -rf /var/lib/apt/lists/*

RUN cd /opt/PX4-Autopilot && make px4_sitl_default

# Micro XRCE-DDS Agent (version from PX4 v1.17.0 docs/en/ros2/user_guide.md:155).
RUN git -c advice.detachedHead=false clone --quiet --depth 1 --branch ${XRCE_AGENT_REF} \
      https://github.com/eProsima/Micro-XRCE-DDS-Agent.git /opt/Micro-XRCE-DDS-Agent \
 && cmake -S /opt/Micro-XRCE-DDS-Agent -B /opt/Micro-XRCE-DDS-Agent/build \
 && cmake --build /opt/Micro-XRCE-DDS-Agent/build -j"$(nproc)" \
 && cmake --install /opt/Micro-XRCE-DDS-Agent/build \
 && ldconfig /usr/local/lib/

# rcS scales link-loss timeouts with `bc` when PX4_SIM_SPEED_FACTOR is set (GROUNDING A.22).
RUN apt-get update -y --quiet \
 && apt-get install -y --quiet --no-install-recommends bc \
 && rm -rf /var/lib/apt/lists/*

ENV PX4_DIR=/opt/PX4-Autopilot \
    PX4_BUILD=/opt/PX4-Autopilot/build/px4_sitl_default

WORKDIR /work
