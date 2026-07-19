"""Module contains model and argument definitions."""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from .antenna import load_antennas

from signalserver_gui import Base


def _fk_pragma_on_connect(dbapi_con, con_record):
    """Add database hook to enable foreign keys."""
    dbapi_con.execute("pragma foreign_keys=ON")


def db_file_init(db_file: str):
    if os.path.isfile(db_file):
        os.remove(db_file)
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    event.listen(engine, "connect", _fk_pragma_on_connect)
    Session = sessionmaker(bind=engine)
    db = Session()
    Base.metadata.create_all(engine)
    load_antennas(db)
    return db


def init(db_path: str):
    """Initialize the sqlite database engine."""
    db_file = os.path.join(db_path, "signalserver_gui.db")
    if not os.path.isfile(db_file):
        db_file_init(db_file)
    engine = create_engine(f"sqlite:///{db_file}", echo=False)
    event.listen(engine, "connect", _fk_pragma_on_connect)
    return engine


# Map all global parameters to their various attributes.
global_args = {
    "terrain_greyscale": {
        "flag": "-t",
        "type": bool,
        "depends": None,
        "hint": "Terrain greyscale background",
    },
    "debug": {
        "flag": "-dbg",
        "type": bool,
        "depends": None,
        "hint": "Verbose debug messages",
    },
    "normalize": {
        "flag": "-ng",
        "type": bool,
        "depends": ["do_p2p_analysis"],
        "hint": "Normalise Path Profile graph",
    },
    "halve": {
        "flag": "-haf",
        "type": int,
        "depends": None,
        "hint": "Halve 1 or 2 (optional)",
    },
    "nothreads": {
        "flag": "-nothreads",
        "type": bool,
        "depends": None,
        "hint": "Turn off threaded processing",
    },
    "elevation_data_dir": {
        "flag": "-sdf",
        "type": str,
        "depends": None,
        "hint": "Directory containing SRTM derived .sdf DEM tiles (may be .gz or .bz2).",
    },
    "lidar_data_dir": {
        "flag": "-lid",
        "type": str,
        "depends": ["use_lidar"],
        "hint": "ASCII grid tile (LIDAR) with dimensions and resolution defined in header.",
    },
    "user_data_dir": {
        "flag": "-udt",
        "type": str,
        "depends": ["use_udt"],
        "hint": "User defined point clutter as decimal co-ordinates: 'latitude,longitude,height'.",
    },
    "clutter_data_files": {
        "flag": "-clt",
        "type": str,
        "depends": None,
        "hint": "MODIS 17-class wide area clutter in ASCII grid format.",
    },
    #    "color_profile": {
    #        "flag": "-color",
    #        "type": str,
    #        "depends": None,
    #        "hint": "File to pre-load .scf/.lcf/.dcf for Signal/Loss/dBm color palette.",
    #    },
}

# Map all plot related parameters to their various attributes.
plot_args = {
    "plot": {
        "id": {
            "flag": None,
            "depends": None,
            "hint": "Auto assigned upon creation.",
            "form": {"type": "ignore"},
        },
        "created": {
            "flag": None,
            "depends": None,
            "hint": "Auto assigned upon creation.",
            "form": {"type": "ignore"},
        },
        "last_updated": {
            "flag": None,
            "depends": None,
            "hint": "Auto update upon modification.",
            "form": {"type": "ignore"},
        },
        "name": {
            "flag": None,
            "depends": None,
            "hint": "Must be unique and at least 8 characters long.",
            "form": {
                "type": "text",
                "parameters": {"placeholder": "Plot Name", "required": True},
            },
        },
        "antenna_id": {
            "flag": None,
            "depends": None,
            "hint": "Antenna profile to use for Station 1 and Station 2. (Required).",
            "form": {
                "type": "select_item",
                "select_type": "antenna",
                "parameters": {"required": True},
            },
        },
        "station1_id": {
            "flag": None,
            "depends": None,
            "hint": "Transmitter station (Required).",
            "form": {
                "type": "select_item",
                "select_type": "station",
                "parameters": {"required": True},
            },
        },
        "station2_id": {
            "flag": None,
            "depends": None,
            "hint": "Receiver station (Required for p2p analysis).",
            "form": {
                "type": "select_item",
                "select_type": "station",
                "parameters": {"required": False},
            },
        },
        "do_p2p_analysis": {
            "flag": None,
            "depends": None,
            "hint": "Enable point-to-point (P2P) analysis between Station 1 (Tx) and Station 2 (Rx). Produces a path profile showing terrain, Fresnel zones, and link budget. Requires Station 2 to be set.",
            "form": {
                "type": "checkbox",
                "parameters": {"default": False, "required": True},
            },
        },
        "use_metric_units": {
            "flag": "-m",
            "depends": None,
            "hint": "Use metric units (kilometers, meters) instead of imperial (miles, feet) for distance and height measurements throughout the analysis.",
            "form": {
                "type": "checkbox",
                "parameters": {"default": True, "required": True},
            },
        },
        "use_lidar": {
            "flag": None,
            "depends": None,
            "hint": "Enable high-resolution LIDAR elevation data for the simulation. LIDAR provides much finer terrain detail than standard SRTM data. Requires LIDAR tiles configured in global settings.",
            "form": {
                "type": "checkbox",
                "parameters": {"default": False, "required": True},
            },
        },
        "use_udt": {
            "flag": None,
            "depends": None,
            "hint": "Enable user-defined terrain/clutter data. Allows custom point clutter (buildings, trees, etc.) to be overlaid on the terrain model. Requires UDT files configured in global settings.",
            "form": {
                "type": "checkbox",
                "parameters": {"default": False, "required": True},
            },
        },
        "use_dbm": {
            "flag": "-dbm",
            "depends": None,
            "hint": "Plot received signal power in dBm instead of field strength in dBuV/m. Use dBm when you need to compare against receiver sensitivity specs (e.g. -100 dBm).",
            "form": {
                "type": "checkbox",
                "parameters": {"default": True, "required": True},
            },
        },
        "use_knife_edge_diffraction": {
            "flag": "-ked",
            "depends": None,
            "hint": "Enable knife-edge diffraction to model signal bending over sharp terrain obstacles (hills, ridges). Already included in ITM/ITWOM models — only needed for simpler models like LOS or FSPL.",
            "form": {
                "type": "checkbox",
                "parameters": {"default": False, "required": True},
            },
        },
        "opacity": {
            "flag": None,
            "depends": None,
            "hint": "Transparency of the coverage overlay on the map. 1.0 = fully opaque, 0.05 = nearly transparent. Lower values let you see the underlying map terrain through the plot.",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 0.05,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.5,
                    "required": True,
                },
            },
        },
        "effective_radiated_power": {
            "flag": "-erp",
            "depends": None,
            "hint": "Total Effective Radiated Power of the transmitter in Watts, referenced to a dipole (dBd). Includes transmitter power plus antenna gain. Note: 0 dBd = 2.14 dBi. Higher ERP = larger coverage area.",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 1,
                    "max": 100000,
                    "step": 1,
                    "default": 10,
                    "units": "Watts",
                    "required": True,
                },
            },
        },
        "frequency": {
            "flag": "-f",
            "depends": None,
            "hint": "Transmitter frequency in MHz (range: 20 MHz to 100,000 MHz). Lower frequencies propagate further and penetrate obstacles better. Above 20 GHz only line-of-sight propagation is modeled.",
            "form": {
                "type": "text",
                "parameters": {
                    "placeholder": "20 - 100000",
                    "units": "MHz",
                    "required": True,
                },
            },
        },
        "radius": {
            "flag": "-R",
            "depends": None,
            "hint": "Maximum analysis radius from the transmitter. Units are miles (imperial) or kilometers (metric) depending on the 'Use Metric Units' setting. Larger radius = longer computation time.",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 5,
                    "max": 75,
                    "step": 5,
                    "default": 25,
                    "units": "miles/kilometers",
                    "required": True,
                },
            },
        },
        "resolution": {
            "flag": "-res",
            "depends": None,
            "hint": "Terrain resolution in pixels per tile. Higher values = finer detail but slower computation. 300 (~900m), 600 (~450m), 1200 (~90m, recommended), 3600 (~30m). LIDAR data uses its own internal resolution.",
            "form": {
                "type": "select",
                "parameters": {
                    "options": [300, 600, 1200, 3600],
                    "default": 1200,
                    "required": True,
                },
            },
        },
        "propagation_model": {
            "flag": "-pm",
            "depends": None,
            "hint": "Radio propagation model to simulate signal behavior. ITM/ITWOM: general-purpose terrain-based models (most accurate). LOS: line-of-sight only. Hata/COST-Hata: urban/suburban mobile. ECC33: UHF broadcasting. SUI: fixed wireless broadband. FSPL: free-space (no terrain). Ericsson: cellular planning. Plane Earth: flat ground reflection. Egli: VHF/UHF empirical. Soil: ground-penetrating.",
            "form": {
                "type": "select_tuple",
                "parameters": {
                    "options": [
                        ("", "none"),
                        (1, "itm"),
                        (2, "los"),
                        (3, "hata"),
                        (4, "ecc33"),
                        (5, "sui"),
                        (6, "cost hata"),
                        (7, "fspl"),
                        (8, "itwom"),
                        (9, "ericsson"),
                        (10, "plane earth"),
                        (11, "egli vhf/uhf"),
                        (12, "soil"),
                    ],
                    "default": "1",
                },
            },
        },
        "propagation_mode": {
            "flag": "-pe",
            "depends": None,
            "hint": "Environment type for the propagation model. Urban: dense buildings, high signal loss. Suburban: moderate buildings and vegetation. Rural: open terrain, minimal obstructions. Affects path loss calculations in Hata, COST-Hata, SUI, and ECC33 models.",
            "form": {
                "type": "select_tuple",
                "parameters": {
                    "options": [
                        ("", "none"),
                        (1, "urban"),
                        (2, "suburban"),
                        (3, "rural"),
                    ]
                },
            },
        },
        "terrain_code": {
            "flag": "-te",
            "depends": None,
            "hint": "Ground surface type affecting signal reflection and absorption. Water: best conductivity, strong reflections. Marsh: wet soil, moderate conductivity. Farmland: average soil. Mountain: rocky, irregular terrain. Desert: dry, low conductivity. Urban: buildings and concrete. Used by ITM/ITWOM for ground constants.",
            "form": {
                "type": "select_tuple",
                "parameters": {
                    "options": [
                        ("", "none"),
                        (1, "water"),
                        (2, "marsh"),
                        (3, "farmland"),
                        (4, "mountain"),
                        (5, "desert"),
                        (6, "urban"),
                    ]
                },
            },
        },
        "terrain_dialectric": {
            "flag": "-terdic",
            "depends": None,
            "hint": "Dielectric constant of the ground surface (2-80). Low values (~2-5): dry soil/rock. High values (~60-80): water/wet ground. Affects signal reflection at ground level. Override this if the terrain code defaults don't match your site.",
            "form": {
                "type": "range",
                "parameters": {"min": 2, "max": 80, "step": 1, "default": 2},
            },
        },
        "terrain_conductivity": {
            "flag": "-tercon",
            "depends": None,
            "hint": "Electrical conductivity of the ground in Siemens/meter (0.0001-0.01). Low values (~0.0001): dry/rocky ground. High values (~0.01): saltwater/wet soil. Affects ground-wave propagation and surface reflections.",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 0.0001,
                    "max": 0.01,
                    "step": 0.0001,
                    "required": False,
                    "default": 0.0001,
                },
            },
        },
        "climate_code": {
            "flag": "-cl",
            "depends": None,
            "hint": "Climate zone affecting atmospheric refractivity and signal propagation. Equatorial: hot/humid, strong ducting. Continental Subtropical: warm inland. Maritime Subtropical: warm coastal. Desert: hot/dry. Continental Temperate: mid-latitude inland. Maritime Temperate (Land/Sea): mid-latitude coastal. Used by ITM/ITWOM models.",
            "form": {
                "type": "select_tuple",
                "parameters": {
                    "options": [
                        ("", "none"),
                        (1, "equatorial"),
                        (2, "continental subtropical"),
                        (3, "maritime subtropical"),
                        (4, "desert"),
                        (5, "continental temperate"),
                        (6, "maritime temperate (land)"),
                        (7, "maritime temperate (sea)"),
                    ]
                },
            },
        },
        "itm_reliability": {
            "flag": "-rel",
            "depends": None,
            "hint": "ITM time reliability (1-99%). The percentage of time the predicted signal level will be met or exceeded. Higher values = more conservative (weaker) predictions. 50% = median. 90%+ recommended for critical links.",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 1,
                    "max": 99,
                    "step": 1,
                    "default": 50,
                    "units": "%",
                },
            },
        },
        "itm_confidence": {
            "flag": "-conf",
            "depends": None,
            "hint": "ITM situation confidence (1-99%). The percentage of similar locations where the prediction is expected to hold. Accounts for variability between locations with similar terrain. 50% = median. Higher = more conservative.",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 1,
                    "max": 99,
                    "step": 1,
                    "default": 50,
                    "units": "%",
                },
            },
        },
        "ground_clutter": {
            "flag": "-gc",
            "depends": None,
            "hint": "Average height of random ground clutter (trees, buildings, etc.) added uniformly across the terrain. Units are feet (imperial) or meters (metric). Simulates obstructions not in the elevation data.",
            "form": {
                "type": "text",
                "parameters": {
                    "placeholder": "0",
                    "units": "feet/meters",
                    "required": False,
                },
            },
        },
        "resample_reduction_factor": {
            "flag": "-resample",
            "depends": ["use_lidar"],
            "hint": "Downsample LIDAR data to speed up computation. Factor 1 = full resolution, 2 = half resolution (50%), 4 = quarter, etc. Use higher factors for quick previews, factor 1 for final analysis.",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 1,
                    "max": 8,
                    "step": 1,
                    "default": 1,
                    "units": "x",
                },
            },
        },
    },
    "antenna": {
        "id": {
            "flag": None,
            "depends": None,
            "hint": "Auto assigned upon creation.",
            "form": {"type": "ignore"},
        },
        "created": {
            "flag": None,
            "depends": None,
            "hint": "Auto assigned upon creation.",
            "form": {"type": "ignore"},
        },
        "last_updated": {
            "flag": None,
            "depends": None,
            "hint": "Auto update upon modification.",
            "form": {"type": "ignore"},
        },
        "name": {
            "flag": "",
            "depends": None,
            "hint": "Must be unique and at least 11 characters long.",
            "form": {
                "type": "text",
                "parameters": {"placeholder": "ABC-123v(4)", "required": True},
            },
        },
        "type": {
            "flag": None,
            "depends": None,
            "hint": "Antenna style.",
            "form": {
                "type": "select",
                "parameters": {
                    "options": [
                        "cardio",
                        "corner",
                        "dipole",
                        "ellipse",
                        "ground",
                        "mobile",
                        "panel",
                        "yagi",
                    ],
                    "default": "dipole",
                },
            },
        },
        "rx_gain": {
            "flag": "-rxg",
            "depends": ["do_p2p_analysis"],
            "hint": "Rx gain dBd (optional for PPA text report)",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 0,
                    "max": 120,
                    "step": 3,
                    "default": 0,
                    "units": "dB",
                },
            },
        },
        "rx_threshhold": {
            "flag": "-rt",
            "depends": None,
            "hint": "Rx Threshold (dB / dBm / dBuV/m)",
            "form": {
                "type": "range",
                "parameters": {
                    "min": -120,
                    "max": 0,
                    "step": 3,
                    "default": 0,
                    "units": "dBm",
                },
            },
        },
        "filename": {
            "flag": "-ant",
            "depends": None,
            "hint": "Antenna pattern file (.ant) converted to .az and .el files on upload.",
            "form": {
                "type": "file",
                "parameters": {"accept": ".ant", "required": True},
            },
        },
    },
    "station": {
        "id": {
            "flag": None,
            "depends": None,
            "hint": "Auto assigned upon creation.",
            "form": {"type": "ignore"},
        },
        "created": {
            "flag": None,
            "depends": None,
            "hint": "Auto assigned upon creation.",
            "form": {"type": "ignore"},
        },
        "last_updated": {
            "flag": None,
            "depends": None,
            "hint": "Auto update upon modification.",
            "form": {"type": "ignore"},
        },
        "name": {
            "flag": "",
            "depends": None,
            "hint": "Must be unique and at least 11 characters long.",
            "form": {
                "type": "text",
                "parameters": {"placeholder": "Station123", "required": True},
            },
        },
        "geography": {
            "flag": None,
            "depends": None,
            "hint": "The country the station physically resides in if outside the United States.",
            "form": {
                "type": "select",
                "parameters": {
                    "options": [
                        "north america",
                        "central america",
                        "south america",
                        "europe",
                        "africa",
                        "asia",
                        "caribbean",
                        "oceania",
                    ]
                },
                "default": "north america",
            },
        },
        "state": {
            "flag": None,
            "depends": None,
            "hint": "The State the station physically resides in.",
            "form": {
                "type": "select",
                "parameters": {
                    "options": [
                        "n/a",
                        "alabama",
                        "alaska",
                        "arizona",
                        "arkansas",
                    ]
                },
            },
        },
        "latitude": {
            "flag": "-lat",
            "depends": None,
            "hint": "Station latitude (decimal degrees) -70/+70",
            "form": {
                "type": "range",
                "parameters": {
                    "min": -70,
                    "max": 70,
                    "step": 0.001,
                    "default": 0.00,
                },
            },
        },
        "longitude": {
            "flag": "-lon",
            "depends": None,
            "hint": "Station longitude (decimal degrees) -180/+180",
            "form": {
                "type": "range",
                "parameters": {
                    "min": -180,
                    "max": 180,
                    "step": 0.001,
                    "default": 0.00,
                },
            },
        },
        "height": {
            "flag": "-txh",
            "depends": None,
            "hint": "Tx Height (above ground)",
            "form": {
                "type": "text",
                "parameters": {
                    "placeholder": "Height AGL",
                    "required": True,
                    "default": 1,
                },
            },
        },
        "polarization": {
            "flag": "-hp",
            "depends": None,
            "hint": "Horizontal Polarisation (default=vertical)",
            "form": {
                "type": "select",
                "parameters": {
                    "options": ["horizontal", "vertical"],
                    "default": "vertical",
                },
            },
        },
        "rotation": {
            "flag": "-rot",
            "depends": None,
            "hint": "(  0.0 - 359.0 degrees, default 0.0) Antenna Pattern Rotation",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 0,
                    "max": 359,
                    "step": 0.1,
                    "default": 0.0,
                },
            },
        },
        "downtilt": {
            "flag": "-dt",
            "depends": None,
            "hint": "( -10.0 - 90.0 degrees, default 0.0) Antenna Downtilt",
            "form": {
                "type": "range",
                "parameters": {
                    "min": -10,
                    "max": 90,
                    "step": 0.1,
                    "default": 0.0,
                },
            },
        },
        "downtilt_direction": {
            "flag": "-dtdir",
            "depends": None,
            "hint": "( 0.0 - 359.0 degrees, default 0.0) Antenna Downtilt Direction",
            "form": {
                "type": "range",
                "parameters": {
                    "min": 0,
                    "max": 359,
                    "step": 0.1,
                    "default": 0.0,
                },
            },
        },
        "rx_height": {
            "flag": "-rxh",
            "depends": ["do_p2p_analysis"],
            "hint": "Rx height above ground (optional. Default=1)",
            "form": {"type": "ignore"},
        },
        "rx_latitude": {
            "flag": "-rla",
            "depends": ["do_p2p_analysis"],
            "hint": "Rx Latitude for PPA (decimal degrees) -70/+70",
            "form": {"type": "ignore"},
        },
        "rx_longitude": {
            "flag": "-rlo",
            "depends": ["do_p2p_analysis"],
            "hint": "Rx Longitude for PPA (decimal degrees) -180/+180",
            "form": {"type": "ignore"},
        },
    },
}
