#! /usr/bin/env python
"""A lightweight web gui for signalserver."""
# TODO(Justin): Remove unused imports
import sys
import os

path = os.path.dirname(sys.modules[__name__].__file__)
path = os.path.join(path, "..")
sys.path.insert(0, path)

import configparser
import functools
import glob
import json
import os
import re
import shutil

import pyproj

from bottle import (
    HTTPError,
    abort,
    delete,
    error,
    get,
    install,
    jinja2_template,
    post,
    redirect,
    request,
    route,
    run,
    static_file,
)

from bottle.ext import sqlalchemy
from sqlalchemy import create_engine, event, literal
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.sql.sqltypes import Boolean, Float, Integer

from signalserver_gui import model
from signalserver_gui import utils
from signalserver_gui.model import global_args, plot_args
from signalserver_gui.antenna import Antenna
from signalserver_gui.station import Station
from signalserver_gui.plot import Plot

# from model import Base, Antenna, Station, Plot, _fk_pragma_on_connect

template = functools.partial(jinja2_template, template_lookup=["templates"])
config = configparser.ConfigParser()


@get("/")
def index():
    """Render the index page."""
    messages = [
        {
            "title": "Welcome!",
            "message": "Welcome to Signal Server GUI!",
        },
    ]

    parts = {"title": "Home"}
    if messages:
        parts["messages"] = messages
    return template("index.html", parts)


@get("/favicon.ico")
def favicon():
    """Serve favicon.ico."""
    return static_file("favicon.ico", root="./static/img")


@get("/img/<filepath:path>")
def server_images(filepath):
    """Serve static image files."""
    return static_file(filepath, root="./static/img")


@get("/js/<filepath:path>")
def server_javascript(filepath):
    """Serve static javascript files."""
    return static_file(filepath, root="./static/js")


@get("/css/<filepath:path>")
def server_stylesheets(filepath):
    """Serve static stylesheet files."""
    return static_file(filepath, root="./static/css")


@get("/download/<filename:path>")
def download(filename):
    """Server download files."""
    return static_file(filename, root="downloads", download=filename)


@error(404)
def error404(error):
    """Render the error page."""
    return "Nothing here, sorry"


def _get_presets_path():
    """Return the path to the presets JSON file."""
    data_dir = config.get("signalservergui", "data_dir", fallback="data")
    return os.path.join(data_dir, "presets.json")


def _load_presets():
    """Load presets from JSON file."""
    presets_path = _get_presets_path()
    if os.path.isfile(presets_path):
        with open(presets_path, "r") as f:
            return json.load(f)
    return {}


def _save_presets(presets):
    """Save presets to JSON file."""
    presets_path = _get_presets_path()
    with open(presets_path, "w") as f:
        json.dump(presets, f, indent=2)


@get("/api/presets")
def get_presets():
    """Return all presets as JSON."""
    from bottle import response
    response.content_type = "application/json"
    return json.dumps(_load_presets())


@post("/api/presets")
def save_preset():
    """Save a new preset from the current form values."""
    from bottle import response
    response.content_type = "application/json"
    preset_name = request.json.get("name")
    preset_values = request.json.get("values")
    if not preset_name or not preset_values:
        response.status = 400
        return json.dumps({"error": "Name and values required"})
    presets = _load_presets()
    presets[preset_name] = preset_values
    _save_presets(presets)
    return json.dumps({"status": "ok"})


@post("/api/presets/delete")
def delete_preset():
    """Delete a preset by name."""
    from bottle import response
    response.content_type = "application/json"
    preset_name = request.json.get("name")
    if not preset_name:
        response.status = 400
        return json.dumps({"error": "Name required"})
    presets = _load_presets()
    if preset_name in presets:
        del presets[preset_name]
        _save_presets(presets)
        return json.dumps({"status": "ok"})
    response.status = 404
    return json.dumps({"error": "Preset not found"})


@get("/api/elevation/highest")
def get_highest_point():
    """Find the highest elevation point within given map bounds using local SDF data."""
    from bottle import response
    import bz2
    import gzip
    import numpy as np

    response.content_type = "application/json"

    try:
        south = float(request.params.get("south"))
        north = float(request.params.get("north"))
        west = float(request.params.get("west"))
        east = float(request.params.get("east"))
    except (TypeError, ValueError):
        response.status = 400
        return json.dumps({"error": "south, north, west, east params required"})

    elev_dir = config.get("signalserver", "elevation_data_dir",
                          fallback=os.path.join(config.get("signalservergui", "data_dir", fallback="data"), "elevation"))

    # Convert east longitude to western convention used by SDF files (360 - lon for eastern hemisphere)
    def to_west_lon(lon):
        if lon > 0:
            return 360 - lon
        return abs(lon)

    # Determine which SDF tiles we need
    import math
    west_w = to_west_lon(west)
    east_w = to_west_lon(east)
    min_w = int(math.floor(min(west_w, east_w)))
    max_w = int(math.ceil(max(west_w, east_w)))
    min_lat = int(math.floor(south))
    max_lat = int(math.ceil(north))

    best_elev = -9999
    best_lat = 0
    best_lng = 0

    for lat_tile in range(min_lat, max_lat):
        for lon_tile in range(min_w, max_w):
            # HD tiles only (3600 resolution)
            tile_name = f"{lat_tile}_{lat_tile + 1}_{lon_tile}_{lon_tile + 1}"
            resolution = 3600
            sdf_path = None

            for suffix in ["-hd.sdf.bz2", "-hd.sdf.gz", "-hd.sdf"]:
                candidate = os.path.join(elev_dir, tile_name + suffix)
                if os.path.isfile(candidate):
                    sdf_path = candidate
                    break

            if not sdf_path:
                continue

            # Read SDF file
            try:
                if sdf_path.endswith('.bz2'):
                    with bz2.open(sdf_path, 'rt') as f:
                        lines = f.readlines()
                elif sdf_path.endswith('.gz'):
                    with gzip.open(sdf_path, 'rt') as f:
                        lines = f.readlines()
                else:
                    with open(sdf_path, 'r') as f:
                        lines = f.readlines()
            except Exception:
                continue

            # Parse header: max_west, min_north, min_west, max_north
            header_max_w = int(lines[0].strip())
            header_min_n = int(lines[1].strip())
            header_min_w = int(lines[2].strip())
            header_max_n = int(lines[3].strip())

            # Parse elevation data into numpy array
            data = np.array([int(l.strip()) for l in lines[4:] if l.strip()], dtype=np.int32)
            if len(data) != resolution * resolution:
                continue
            grid = data.reshape(resolution, resolution)

            # SDF grid: rows go south to north, cols go west to east
            # Lat range: header_min_n to header_max_n
            # Lon range (western): header_min_w to header_max_w
            lat_step = (header_max_n - header_min_n) / resolution
            lon_step = (header_max_w - header_min_w) / resolution

            # Clip to requested bounds (in western lon convention)
            row_start = max(0, int((south - header_min_n) / lat_step))
            row_end = min(resolution, int(math.ceil((north - header_min_n) / lat_step)))
            col_start = max(0, int((min(west_w, east_w) - header_min_w) / lon_step))
            col_end = min(resolution, int(math.ceil((max(west_w, east_w) - header_min_w) / lon_step)))

            if row_start >= row_end or col_start >= col_end:
                continue

            sub = grid[row_start:row_end, col_start:col_end]
            if sub.size == 0:
                continue

            max_idx = np.argmax(sub)
            max_val = sub.flat[max_idx]

            if max_val > best_elev:
                best_elev = int(max_val)
                local_row, local_col = np.unravel_index(max_idx, sub.shape)
                best_lat = header_min_n + (row_start + local_row) * lat_step
                # Convert western lon back to standard lon
                w_lon = header_min_w + (col_start + local_col) * lon_step
                if w_lon > 180:
                    best_lng = 360 - w_lon
                else:
                    best_lng = -w_lon

    if best_elev <= 0:
        return json.dumps({"error": "No elevation data found for this area"})

    return json.dumps({
        "elevation": best_elev,
        "lat": round(best_lat, 5),
        "lng": round(best_lng, 5)
    })


@get("/api/elevation/point")
def get_elevation_at_point():
    """Get elevation at a specific lat/lng using local HD SDF data."""
    from bottle import response
    import bz2
    import gzip
    import math

    response.content_type = "application/json"

    try:
        lat = float(request.params.get("lat"))
        lng = float(request.params.get("lng"))
    except (TypeError, ValueError):
        response.status = 400
        return json.dumps({"error": "lat and lng params required"})

    elev_dir = config.get("signalserver", "elevation_data_dir",
                          fallback=os.path.join(config.get("signalservergui", "data_dir", fallback="data"), "elevation"))

    # Convert to western longitude convention
    west_lon = (360 - lng) if lng > 0 else abs(lng)
    lat_tile = int(math.floor(lat))
    lon_tile = int(math.floor(west_lon))

    tile_name = f"{lat_tile}_{lat_tile + 1}_{lon_tile}_{lon_tile + 1}"
    resolution = 3600
    sdf_path = None

    for suffix in ["-hd.sdf.bz2", "-hd.sdf.gz", "-hd.sdf"]:
        candidate = os.path.join(elev_dir, tile_name + suffix)
        if os.path.isfile(candidate):
            sdf_path = candidate
            break

    if not sdf_path:
        return json.dumps({"elevation": None, "error": "No elevation data for this location"})

    try:
        if sdf_path.endswith('.bz2'):
            with bz2.open(sdf_path, 'rt') as f:
                lines = f.readlines()
        elif sdf_path.endswith('.gz'):
            with gzip.open(sdf_path, 'rt') as f:
                lines = f.readlines()
        else:
            with open(sdf_path, 'r') as f:
                lines = f.readlines()
    except Exception:
        return json.dumps({"elevation": None, "error": "Failed to read elevation data"})

    header_max_w = int(lines[0].strip())
    header_min_n = int(lines[1].strip())
    header_min_w = int(lines[2].strip())
    header_max_n = int(lines[3].strip())

    lat_step = (header_max_n - header_min_n) / resolution
    lon_step = (header_max_w - header_min_w) / resolution

    row = int((lat - header_min_n) / lat_step)
    col = int((west_lon - header_min_w) / lon_step)

    if row < 0 or row >= resolution or col < 0 or col >= resolution:
        return json.dumps({"elevation": None, "error": "Point outside tile bounds"})

    # Read specific line (header + row*resolution + col)
    line_idx = 4 + row * resolution + col
    if line_idx >= len(lines):
        return json.dumps({"elevation": None, "error": "Data index out of range"})

    elevation = int(lines[line_idx].strip())
    return json.dumps({"elevation": elevation, "lat": lat, "lng": lng})


@get("/search")
def search(db):
    """Render the station search page."""
    search_type = request.query.type
    search = request.query.q
    search_type_col = literal("plot").label("type")
    if search_type == "stations":
        query = db.query(Station).filter(Station.name.like(f"%{search}%"))
    elif search_type == "antennas":
        query = db.query(Antenna).filter(Antenna.name.like(f"%{search}%"))
    elif search_type == "plots":
        query = db.query(Plot).filter(Plot.name.like(f"%{search}%"))
    else:
        search_type_col = literal("plot").label("type")
        q1 = db.query(
            Plot.id.label("id"), Plot.name.label("name"), search_type_col
        ).where(Plot.name.like(f"%{search}%"))
        search_type_col = literal("antenna").label("type")
        q2 = db.query(
            Antenna.id.label("id"),
            Antenna.name.label("name"),
            search_type_col,
        ).where(Antenna.name.like(f"%{search}%"))
        search_type_col = literal("station").label("type")
        q3 = db.query(
            Station.id.label("id"),
            Station.name.label("name"),
            search_type_col,
        ).where(Station.name.like(f"%{search}%"))
        query = q1.union(q2).union(q3)
    if query and request.query.sort_by:
        # print(dir(query))
        if request.query.sort_by == "id":
            if request.query.sort_dir == "desc":
                query = query.order_by(Station.id.desc())
            else:
                query = query.order_by(Station.id.asc())
        elif request.query.sort_by == "name":
            if request.query.sort_dir == "desc":
                query = query.order_by(Station.name.desc())
            else:
                query = query.order_by(Station.name.asc())
        elif request.query.sort_by == "type":
            if request.query.sort_dir == "desc":
                query = query.order_by(search_type_col.desc())
            else:
                query = query.order_by(search_type_col.asc())
    results = query.all()
    parts = {
        "search_type": search_type,
        "search": search,
        "sort_by": request.query.sort_by,
        "sort_dir": request.query.sort_dir,
        "results": results,
    }
    return template("search.html", parts)


@get("/<item_type>s")
def list_items(item_type, db):
    """Render list items page."""
    if item_type == "station":
        items = db.query(Station).all()
    elif item_type == "antenna":
        items = db.query(Antenna).all()
    elif item_type == "plot":
        items = db.query(Plot).all()
    else:
        redirect("/")
    parts = {"type": item_type, "items": items}
    return template("list.html", parts)


@get("/plot/<id:int>/generate")
def plot_generate(id, db):
    """Render the generate plot page."""
    q = db.query(Plot).filter_by(id=id)
    item = q.first()
    if item:
        utils.generate(config, item)
        redirect(f"/plot/{id}/files")
    else:
        redirect(f"/")


@get("/plot/<id:int>/files")
def plot_files(id, db):
    """Show available file for the current plot."""
    q = db.query(Plot).filter_by(id=id)
    item = q.first()
    if item:
        files = [
            (
                os.path.basename(file),
                os.path.join(
                    os.path.basename(os.path.dirname(file)), os.path.basename(file)
                ),
            )
            for file in glob.glob(f"downloads/{item.id}/*")
        ]
        grouped_files = {
            "Analysis Report": [],
            "KML": [],
            "Zip": [],
            "Image": [],
            "Other": [],
        }
        for file in files:
            if re.match(
                r".+(\.txt|\.json|_curvature|_fresnel|_fresnel60|_profile|_reference)$",
                file[0],
            ):
                grouped_files["Analysis Report"].append(file)
            elif re.match(r".+\.(kml|kmz)$", file[0]):
                grouped_files["KML"].append(file)
            elif re.match(r".+\.(zip)$", file[0]):
                grouped_files["Zip"].append(file)
            elif re.match(r".+\.(png|jpg|bmp|ppm)$", file[0]):
                grouped_files["Image"].append(file)
            else:
                grouped_files["Other"].append(file)
        # print("File Count:", len(files))
        if len(files) == 0:
            redirect(f"/plot/{id}/generate")
        parts = {
            "type": "plot",
            "item": item,
            "files": grouped_files,
            "image_type": config["convert"]["output_type"],
        }
        return template("files.html", parts)
    else:
        redirect(f"/")


@get("/<item_type>/<id:int>/delete")  # Delete confirmation page
@post(
    "/<item_type>/<id:int>/delete"
)  # Delete the station and redirect to stations list
def delete_item(item_type, id, db):
    """Delete item and render the item list page."""
    messages = []
    parts = {}
    if item_type == "station":
        item_class = Station
    elif item_type == "antenna":
        item_class = Antenna
    elif item_type == "plot":
        item_class = Plot
        antennas = db.query(Antenna.id.label("id"), Antenna.name.label("name")).all()
        stations = db.query(Station.id.label("id"), Station.name.label("name")).all()
        parts.update(
            {
                "antennas": antennas,
                "stations": stations,
            }
        )
    else:
        redirect("/")
    if request.method == "POST":
        # dirty_item = db.query(item_class).filter_by(id=id).first()
        dirty_item = db.query(item_class).get(id)
        name = dirty_item.name
        if (
            (
                item_type == "antenna"
                and db.query(Plot).filter_by(antenna_id=id).count() == 0
            )
            or (
                item_type == "station"
                and db.query(Plot).filter_by(station1_id=id).count() == 0
            )
            or (
                item_type == "station"
                and db.query(Plot).filter_by(station2_id=id).count() == 0
            )
            or item_type == "plot"
        ):
            try:
                antenna_type = dirty_item.type if item_type == "antenna" else ""
                db.delete(dirty_item)
                if item_type == "antenna":
                    for f in glob.glob(
                        os.path.join("data/antennas", antenna_type, name + ".*")
                    ):
                        os.remove(f)
                if item_type == "plot":
                    for f in glob.glob(f"downloads/{id}/*"):
                        os.remove(f)
                    os.rmdir(f"downloads/{id}")
            except Exception as e:
                messages.append(
                    {
                        "message": e,
                        "title": f"Deleting {item_type} {name} failed.",
                        "type": "danger",
                    }
                )

            else:
                redirect(f"/{item_type}s?message=DeleteSuccessful")
        else:
            messages.append(
                {
                    "message": "Cannot delete. One or more plots depend on this item.",
                    "title": f"Deleting {item_type} {name} failed.",
                    "type": "danger",
                }
            )

    if id:
        item = db.query(item_class).filter_by(id=id).first()
    else:
        item = request.forms
    parts["item"] = item
    parts.update(
        {
            "request": request,
            "type": item_type,
            "table": item_class.__table__,
            "args": plot_args,
        }
    )
    if messages:
        parts["messages"] = messages
    return template("delete.html", parts)


@get("/<item_type>/<id:int>/<action>")  # Edit station
@post("/<item_type>/<id:int>/<action>")  # Update station and render updated edit page
@get("/<item_type>s/<action>")
@post("/<item_type>s/<action>")
def action_item(item_type, action, db, id=0):
    """Render the new item page."""
    if action not in ["new", "edit"]:
        redirect("/")
    messages = []
    parts = {}
    if item_type == "station":
        item_class = Station
    elif item_type == "antenna":
        item_class = Antenna
    elif item_type == "plot":
        item_class = Plot
        antennas = db.query(Antenna.id.label("id"), Antenna.name.label("name")).all()
        stations = db.query(Station.id.label("id"), Station.name.label("name")).all()
        parts.update(
            {
                "antennas": antennas,
                "stations": stations,
            }
        )
    else:
        redirect("/")

    if id:
        item = db.query(item_class).filter_by(id=id).first()
    else:
        item = request.forms
    parts["item"] = item

    if request.method == "POST":
        if item_type == "plot" and len(request.forms.get("name")) < 8:
            messages.append(
                {
                    "message": "Name must be 8 characters or longer.",
                    "title": f"Item creation failed.",
                    "type": "danger",
                }
            )
        elif item_type == "plot" and " " in request.forms.get("name"):
            messages.append(
                {
                    "message": "Plot names cannot contain spaces.",
                    "title": f"Item creation failed.",
                    "type": "danger",
                }
            )
        elif (
            item_type == "plot"
            and request.forms.get("do_p2p_analysis")
            and request.forms.get("station2_id") == ""
        ):
            messages.append(
                {
                    "message": "Propagation analysis requires both Station 1 and Station 2 to be set.",
                    "title": f"Item creation failed.",
                    "type": "danger",
                }
            )
        elif item_type == "plot" and request.forms.get(
            "station1_id"
        ) == request.forms.get("station2_id"):
            messages.append(
                {
                    "message": "Station 1 and Station 2 must be different.",
                    "title": f"Item creation failed.",
                    "type": "danger",
                }
            )
        elif item_type == "station" and (
            not request.forms.get("latitude") or not request.forms.get("longitude")
            or float(request.forms.get("latitude", 0)) == 0.0
            or float(request.forms.get("longitude", 0)) == 0.0
        ):
            messages.append(
                {
                    "message": "Latitude and Longitude must be set and cannot be zero.",
                    "title": f"Item creation failed.",
                    "type": "danger",
                }
        )
        elif action == "new":
            try:
                antenna_file = request.files.get("filename")
                if antenna_file:
                    original_filename, ext = os.path.splitext(antenna_file.filename)
                    if ext != ".ant":
                        raise (Exception(f"{ext} - Unsupported filetype."))
                    save_path = f"data/antennas/{request.forms.get('type')}/"
                    if not os.path.exists(save_path):
                        os.makedirs(save_path)
                    filename = request.forms.get("name") + ".ant"
                    file_path = os.path.join(save_path, filename)
                    antenna_file.save(file_path, overwrite=True)
                    utils.convert_ant_file(file_path)
                    request.forms["filename"] = request.forms.get("name")
                # new_item = item_class(**request.forms)
                params = {}
                for col in item_class.__table__.columns:
                    value = request.forms.get(col.name)
                    if col.name in ["id", "created", "last_updated"]:
                        pass
                    elif isinstance(col.type, Boolean):
                        if value:
                            params[col.name] = True
                        else:
                            params[col.name] = False
                    elif value:
                        if isinstance(col.type, Integer):
                            params[col.name] = int(value)
                        elif isinstance(col.type, Float):
                            params[col.name] = float(value)
                        else:
                            params[col.name] = value
                new_item = item_class(**params)

                db.add(new_item)
                db.commit()

            except Exception as e:
                db.rollback()
                messages.append(
                    {"message": e, "title": f"Item creation failed.", "type": "danger"}
                )
            else:
                redirect(
                    f"/{item_type}/{new_item.id}/edit?message=ItemAddedSuccessfully"
                )
        else:
            try:
                dirty_item = db.get(item_class, id)
                # print(f"item of page:{item_class.__table__.columns}")
                for col in item_class.__table__.columns:
                    value = request.forms.get(col.name)
                    # print(f"{col}: {value}")
                    if item_type == "plot" and col.name == "name" and len(value) < 8:
                        messages.append(
                            {
                                "message": "Name must be 8 characters or longer.",
                                "title": f"Item update failed.",
                                "type": "danger",
                            }
                        )
                        break

                    if isinstance(col.type, Boolean):
                        if value != None:
                            setattr(dirty_item, col.name, True)
                        else:
                            setattr(dirty_item, col.name, False)
                    elif value:
                        if isinstance(col.type, Integer):
                            setattr(dirty_item, col.name, int(value))
                        elif isinstance(col.type, Float):
                            setattr(dirty_item, col.name, float(value))
                        else:
                            setattr(dirty_item, col.name, value)
                # db.query(item_class).filter_by(id=id).update(request.forms)
                db.commit()
            except Exception as e:
                db.rollback()
                messages.append(
                    {"message": e, "title": f"Item update failed.", "type": "danger"}
                )

            else:
                messages.append(
                    {"message": f"Item update successful.", "type": "success"}
                )

    parts.update(
        {
            "request": request,
            "type": item_type,
            "action": action,
            "table": item_class.__table__,
            "args": plot_args,
        }
    )
    if messages:
        parts["messages"] = messages
    return template("form.html", parts)


@get("/<item_type>/<id:int>")
def view_item(item_type, id, db):
    """Render the item view page."""
    if item_type == "station":
        q = db.query(Station).filter_by(id=id)
    elif item_type == "antenna":
        q = db.query(Antenna).filter_by(id=id)
    elif item_type == "plot":
        q = db.query(Plot).filter_by(id=id)
    else:
        redirect("/")
    item = q.first()
    parts = {"type": item_type, "item": item}
    if item_type == "plot" and item.do_p2p_analysis and item.station2:
        geodesic = pyproj.Geod(ellps="WGS84")
        _, _, distance = geodesic.inv(
            item.station1.longitude,
            item.station1.latitude,
            item.station2.longitude,
            item.station2.latitude,
        )
        parts["p2p_distance_km"] = distance / 1000.0
    return template("view.html", parts)


@get("/clean")
def clean_generated_files():
    for file in glob.glob(f"downloads/*"):
        shutil.rmtree(file)
    redirect("/")


@get("/config")
def get_config():
    """Render the config page."""
    tools = {
        "signalserver": (
            config["signalserver"]["path"],
            True if utils.which(config["signalserver"]["path"]) else False,
        ),
        "signalserver": (
            config["signalserver"]["path"],
            True if utils.which(config["signalserver"]["path"] + "HD") else False,
        ),
        "convert": (
            config["convert"]["path"],
            True if utils.which(config["convert"]["path"]) else False,
        ),
    }
    parts = {
        "title": "Config",
        "config": config,
        "tools": tools,
        "global_args": global_args,
    }
    return template("config.html", parts)


@get("/map_popup")
def map_popup(db):
    """Render the map popup page."""
    geotiff = request.query.geotiff
    map_lat = config.get("signalservergui", "map_latitude", fallback="35.502")
    map_lng = config.get("signalservergui", "map_longitude", fallback="23.957")
    map_zoom = config.get("signalservergui", "map_zoom", fallback="12")
    stations = db.query(Station).all()
    stations_json = json.dumps([
        {"name": s.name, "lat": s.latitude, "lng": s.longitude, "height": s.height}
        for s in stations if s.latitude and s.longitude
    ])
    return template("map_popup.html", geotiff=geotiff,
                    map_lat=map_lat, map_lng=map_lng, map_zoom=map_zoom,
                    stations_json=stations_json)


if __name__ == "__main__":
    if os.path.isfile("config.ini"):
        try:
            config.read("config.ini")
            # Check config for required sections and items
            if "signalservergui" not in config:
                raise (
                    Exception("Missing required 'signalserver-gui' section in config.")
                )
            elif "data_dir" not in config["signalservergui"]:
                raise (
                    Exception(
                        "Missing required 'data_dir' value in 'signalservergui' section of config."
                    )
                )
            elif "output_dir" not in config["signalservergui"]:
                raise (
                    Exception(
                        "Missing required 'output_dir' value in 'signalservergui' section of config."
                    )
                )
            elif "database_dir" not in config["signalservergui"]:
                raise (
                    Exception(
                        "Missing required 'database_dir' value in 'signalservergui' section of config."
                    )
                )
            elif "signalserver" not in config:
                raise (Exception("Missing required 'signalserver' section in config."))
            elif "path" not in config["signalserver"]:
                raise (
                    Exception(
                        "Missing required 'path' value in 'signalserver' section of config."
                    )
                )
            elif "convert" not in config:
                raise (Exception("Missing required 'convert' section in config."))
            elif "path" not in config["convert"]:
                raise (
                    Exception(
                        "Missing required 'path' value in 'convert' section of config."
                    )
                )

            if "antenna_profiles_dir" not in config["signalserver"]:
                config["signalserver"]["antenna_profiles_dir"] = os.path.join(
                    config["signalservergui"]["data_dir"], "antennas"
                )
            if "elevation_data_dir" not in config["signalserver"]:
                config["signalserver"]["elevation_data_dir"] = os.path.join(
                    config["signalservergui"]["data_dir"], "elevation"
                )
            if "lidar_data_dir" not in config["signalserver"]:
                config["signalserver"]["lidar_data_dir"] = os.path.join(
                    config["signalservergui"]["data_dir"], "lidar"
                )
            if "user_data_dir" not in config["signalserver"]:
                config["signalserver"]["user_data_dir"] = os.path.join(
                    config["signalservergui"]["data_dir"], "user"
                )
            if "clutter_data_dir" not in config["signalserver"]:
                config["signalserver"]["clutter_data_dir"] = os.path.join(
                    config["signalservergui"]["data_dir"], "clutter"
                )
            if "color_profiles_dir" not in config["signalserver"]:
                config["signalserver"]["color_profiles_dir"] = os.path.join(
                    config["signalservergui"]["data_dir"], "color_profiles"
                )
            if "color_profile" not in config["signalserver"]:
                config["signalserver"]["color_profile"] = os.path.join(
                    config["signalserver"]["color_profiles_dir"], "rainbow.dcf"
                )

            if "kmz_conv_path" not in config["signalserver"]:
                config["signalserver"]["kmz_conv_path"] = None

        except Exception as e:
            print(
                "Invalid config.ini, Missing mandatory settings. Exiting...",
                e,
            )
            exit()
    else:
        print("No config.ini preset. Exiting...")
        exit()
    engine = model.init(config["signalservergui"]["database_dir"])
    plugin = sqlalchemy.Plugin(
        engine,
        model.Base.metadata,
        keyword="db",
        create=True,
        commit=True,
        use_kwargs=False,
    )
    install(plugin)
    run(
        host=config["signalservergui"]["address"],
        port=int(config["signalservergui"]["port"]),
        reloader=True,
        debug=True,
    )
