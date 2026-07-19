# Signal Server GUI

Signal Server GUI is designed as a companion to Signal Server. Signal Server GUI provides a simple and intuitive interface to manage the many configuration options available within Signal Server. This web interface allows you to build and save three item types (Stations, Antennas, and Plots). As you develop plots you are afforded opportunity to manipulate some of the many parameters which can affect propagation. Reasonable default values are provided, which can be changed as you develop and refine your model.

Glompos21: Added the ability to show the plot on top of a map and misc fix/updates

## Getting Started

### Installation

Clone repository

```shell
git clone https://github.com/glompos21/signalserver_gui.git
cd signalserver_gui
git submodule update --init --recursive
```

Complile Signal-Server
See [Signal-Server Readme.md](./Signal-Server/README.md#L61)

Install python dependencies

```shell
cd signalserver_gui
python -m venv .venv
source .venv/bin/activate
pip install -rrequirements.txt
```

Install kmzToGeoTiff.sh
```shell
sudo apt install gdal-bin
```

### Configuration

Update required parameters config.ini

Config entries listed below are required.

```
[signalservergui]
data_dir = data
output_dir = downloads
database_dir = db

[signalserver]
path = /usr/bin/signalserver

[convert]
path = /usr/bin/convert
output_type = png
```

- `signalservergui` - Config section with signalservergui settings
  - `data_dir` - Specifies the directory containing various types of data. This option is used to automatically infer the subdirectories for all specific data types.
    - **Example**
      - data_dir = data
      - *(inferred)* elevation_data_dir = data/elevation
      - *(inferred)* lidar_data_dir = data/lidar
      - *(inferred)* user_data_dir = data/user
      - *(inferred)* clutter_data_dir = data/clutter
      - *(inferred)* antenna_profiles_dir = data/antennas
      - *(inferred)* color_profiles_dir = data/color_profiles
      - *(inferred)* color_profile = data/color_profiles/rainbow.dcf
  - `output_dir` - Specifies the directory into which signalservergui will generate files and make available for download.
    - Each time a plot is generate, a subfolder will be created using the plot_id. This folder will contain all files available for that plot.
  - `database_dir` - Specifies the directory where the sqlite database (signalserver_gui.db) will be created.
- `signalserver` - Config section with signalserver settings
  - `path` - Specifies the path to the signal server binary. Signal Server GUI assumes the signalserverHD and signalserverLIDAR binaries are co-located with the base signalserver binary.
    - **Example**
      - path = /usr/bin/signalserver
      - *(inferred)* /usr/bin/signalserverHD
      - *(inferred)* /usr/bin/signalserverLIDAR
- `convert` - Config section with convert settings
  - `path` - Specifies the path to the convert binary. Convert is included with the ImageMagick suite of tools.
  - `output_type` - Specifies the preferred image format for graphics. Recommend `png` to allow image transparency.
### Elevation data
The data needs to be download and placed on data/elevation
More information on [Signal-Server Readme.md](./Signal-Server/README.md#L159).

Another source of data is: [https://dwtkns.com/srtm30m/](https://dwtkns.com/srtm30m/)

#### Converting .hgt to .sdf files

Signal Server requires elevation data in `.sdf` format. Raw SRTM data comes as `.hgt` files and must be converted using the `srtm2sdf` utilities included in `Signal-Server/utils/sdf/usgs2sdf/`.

**Build the conversion tools first:**
```shell
cd Signal-Server/utils/sdf/usgs2sdf
cmake .
make
```

This produces two binaries:
- `srtm2sdf` — converts 3-arc-second (90m) `.hgt` files to standard `.sdf` (use with `-res 1200` or lower)
- `srtm2sdf-hd` — converts 1-arc-second (30m) `.hgt` files to HD `.sdf` (use with `-res 3600`)

**Standard resolution (90m) — recommended for most use:**
```shell
cd data/elevation
srtm2sdf -d /dev/null N35E023.hgt
# produces: 35_36_337_338.sdf (naming uses western longitude convention)
```

**HD resolution (30m) — slower but finer detail:**
```shell
cd data/elevation
srtm2sdf-hd -d /dev/null N35E023.hgt
# produces: 35_36_337_338-hd.sdf
```

**Batch convert all .hgt files:**
```shell
cd data/elevation

# Standard resolution
for file in *.hgt; do srtm2sdf -d /dev/null "$file"; done

# HD resolution
for file in *.hgt; do srtm2sdf-hd -d /dev/null "$file"; done
```

**Compress to save disk space** (Signal Server reads `.bz2` and `.gz` natively):
```shell
bzip2 *.sdf
```

> **Note:** Resolution must match tile format. Standard `.sdf` tiles work with `-res 300/600/1200`. HD `-hd.sdf` tiles require `-res 3600`. Using mismatched resolution will result in "SDF file not found" warnings and flat (sea-level) terrain.

### Usage

Starting Signal Server GUI:

```shell
cd signalserver_gui
source .venv/bin/activate
python -m signalserver_gui
    (Bottle server console log)...
    Listening on http://localhost:8080/
```

Once signalserver_gui is running, open a browser to the url indicated
in the console log. 

    Example: http://localhost:8080/

### Testing

Populate database with sample sites and plots.

**Caution:**
    **Loading test data with re-initialize database and all existing data will be lost.**

```shell
$ cd signalserver_gui
    (No output)
$ source .venv/bin/activate
    (No output)
$ python -m db.test_init
```

# Docker

The current app can be build into a docker image.
run:

```console
docker compose build
```

```console
docker compose up
```