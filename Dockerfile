# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    g++ \
    cmake \
    make  \
    zlib1g-dev \
    libbz2-dev \
    imagemagick \
    libspdlog-dev \
    unzip \
    gdal-bin && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
# COPY Signal-Server/build/signalserver* /app/bin/
COPY Signal-Server /app/Signal-Server

WORKDIR /app/Signal-Server

# Build the project
RUN rm -rf build && mkdir build && \
    cd build && \
    cmake ../src && \
    make

WORKDIR /app
COPY requirements.txt /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the current directory contents into the container at /app
COPY signalserver_gui /app/signalserver_gui
COPY static /app/static
COPY templates /app/templates
COPY kmzToGeoTiff.sh /app
COPY db /app/db

# Make port 8080 available to the world outside this container
EXPOSE 8080

# Define environment variable
# ENV NAME World

RUN apt-get update && apt-get install -y \
    unzip \
    gdal-bin && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Run app.py when the container launches
CMD ["python", "/app/signalserver_gui/__main__.py"]
