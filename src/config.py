"""Configuration settings for the media pre-processing system."""

import os
from pathlib import Path
from typing import Dict, List, Tuple, Union

# Default input and output directories
DEFAULT_INPUT_DIR = "input"
DEFAULT_OUTPUT_DIR = "output"

# File extensions to be processed
SUPPORTED_EXTENSIONS = {
    'image': ['.jpg', '.jpeg', '.dng', '.arw'],
    'video': ['.mp4'],
}

# Lowercase and 3-letter extension mapping
EXTENSION_MAPPING = {
    '.jpeg': '.jpg',
    '.dng': '.dng',
    '.arw': '.arw',
    '.mp4': '.mp4',
}

# Device identification patterns
DEVICE_PATTERNS = {
    'dji_drone': {
        'filename_patterns': ['DJI_', 'Mavic3Pro'],
        'metadata_patterns': {
            'make': ['Hasselblad', 'DJI'],
            'model': ['L2D-20c', 'Mavic3Pro'],
            'product_name': ['DJIMavic3Pro'],
            'manufacturer': ['DJI'],
        }
    },
    'sony_camera': {
        'filename_patterns': ['DSC'],
        'metadata_patterns': {
            'make': ['SONY'],
            'model': ['ILCE-7M4'],
            'devicemanufacturer': ['Sony'],   # For MP4 files
            'devicemodelname': ['ILCE-7M4'],  # For MP4 files
        }
    },
    'dji_rc_pro': {
        'filename_patterns': ['screen-', 'RCPro'],
        'metadata_patterns': {
            'make': ['DJI'],
            'model': ['RCPro'],
            # Screen recordings might not have specific metadata identifiers
            # We'll rely more on filename patterns for these
        }
    }
}

# Output filename patterns
# These will be formatted with metadata extracted from the files
FILENAME_PATTERNS = {
    ('dji_drone', 'image'): '{date}-{time}-{sequence}-DJI-{model}-{focal_length}{ext}',
    ('dji_drone', 'video'): '{date}-{time}-{resolution}-{fps}-{duration}-DJI-{model}{ext}',
    ('sony_camera', 'image'): '{date}-{time}-{shutter_count}-{make}-{model}{ext}',
    ('sony_camera', 'video'): '{date}-{time}-{resolution}-{fps}-{duration}-{make}-{model}{ext}',
    ('dji_rc_pro', 'video'): '{date}-{time}-{resolution}-{fps}-{duration}-{make}-{model}{ext}',
    'default': '{date}-{time}-{make}-{model}{ext}'
}

# Processed files tracking
# Store the database in the repo folder
PROCESSED_FILES_DB = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.preprocess_media_files.db')

# Timezone configuration - can be overridden via CLI
DEFAULT_TIMEZONE = 'local'  # 'local' means use system timezone
