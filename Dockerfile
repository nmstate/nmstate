#docker.io/library/.deb # Base image matching your Ubuntu version
FROM ubuntu:latest
# Update package lists
#RUN apt-get -y install nmstate
RUN apt-get update && apt-get install -y \
    autoconf \
    build-essential \
    cmake \
    git \
    libcairo2-dev \
    libffi-dev \
    libssl-dev \
    pkg-config \
    python3-dev \
    python3-pip \
    valgrind

ENTRYPOINT ["usr/bin/nmstatectl"]

# Install dependencies (adjust if needed)
RUN apt-get install -y python3-pip build-essential
#RUN pip3 install -r requirements.txt
# Install nmstate using pip
#RUN pip3 install nmstate
RUN apt-get install -y git
RUN git clone https://github.com/nmstate/nmstate.git

# (Optional) Specify any additional commands or configuration for nmstate

# Set the working directory (optional)
WORKDIR /nmstate
RUN pip3 install -r rust/src/python/requirements.txt
#RUN python3 rust/src/python/setup.py install --user

# Build nmstate (assuming you want the libraries)
RUN cd nmstate && mkdir build && cd build && cmake .. && make

# (Optional) Install nmstate within the container (for testing)
RUN cd nmstate && make install


# Clean up (optional)
RUN rm -rf /nmstate

# (Optional) Copy your application code or scripts here

# Set the command to be executed when the container starts
#CMD ["python3", "-c", "import nmstate"]  # Replace with your nmstate script or application

# (Optional) Expose ports if needed for network access
# EXPOSE <port number>

