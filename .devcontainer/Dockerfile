# Use a standard Debian image as the base
FROM mcr.microsoft.com/devcontainers/base:debian

# Install system-level dependencies like ffmpeg and build tools using apt
RUN sudo apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && sudo apt-get -y install --no-install-recommends ffmpeg build-essential cmake

# Install Miniconda (a lightweight version of Conda)
USER codespace
WORKDIR /home/codespace
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O miniconda.sh \
    && bash miniconda.sh -b -p /home/codespace/miniconda \
    && rm miniconda.sh
ENV PATH="/home/codespace/miniconda/bin:${PATH}"

# Initialize Conda for the bash shell
RUN conda init bash