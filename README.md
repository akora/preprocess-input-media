# Media File Pre-Processing System

A modular system for pre-processing media files from various sources, including DJI Mavic 3 Pro drone, Sony A7 IV camera, and DJI RC Pro controller screen recordings.

## Overview

This system analyzes input files using exiftool to extract metadata, renames files, and organizes them in a structured way to help with post-processing.

### Features

- Analyzes media files from different sources
- Extracts metadata and creation timestamps
- Renames files based on configurable patterns
- Organizes files into photos/YYYY/YYYY-MM/YYYY-MM-DD and videos/YYYY/YYYY-MM/YYYY-MM-DD folder structure
- Handles various file types (JPEG, RAW, MP4)
- Provides source-specific processing for different devices
- Detects and skips previously processed files
- Special handling for Sony ARW (RAW) files with proper timestamp extraction

### Supported Sources

- DJI Mavic 3 Pro drone (photos and videos)
- Sony A7 IV digital camera (photos and videos)
- DJI RC Pro controller (screen recordings)

## Installation

1. Clone this repository:

   ```bash
   git clone https://github.com/yourusername/preprocess-input-media.git
   cd preprocess-input-media
   ```

2. Create and activate a virtual environment:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Ensure exiftool is installed on your system.

## Usage

The system provides two ways to run the preprocessing:

### Command Line Interface

Use the `process_media.py` script to process files with command-line options:

```bash
# Basic usage with default parameters
./process_media.py

# Specify custom input and output directories
./process_media.py --input /path/to/media --output /path/to/output

# Process recursively with timezone specification
./process_media.py --input /path/to/media --output /path/to/output --recursive --timezone UTC

# Dry run to show what would be done without processing
./process_media.py --dry-run

# Remove files after successful processing
./process_media.py --input /path/to/media --output /path/to/output --remove-processed
```

### Alternative Usage

You can also use the Python module directly:

```bash
python -m src.main --input /path/to/input/directory --output /path/to/output/directory
```

### Command Line Parameters

| Parameter | Short | Description |
|-----------|-------|-------------|
| `--input` | `-i`  | Input directory containing media files |
| `--output` | `-o` | Output directory for processed files |
| `--timezone` | `-tz` | Timezone to use for timestamps (default: system local timezone) |
| `--recursive` | `-r` | Recursively process files in subdirectories |
| `--dry-run` | | Show what would be done without actually processing files |
| `--remove-processed` | | Remove successfully processed files from the input directory |

## Directory Structure

The system organizes processed files into the following structure:

```text
output/
├── photos/             # All image files (for use with Luminar Neo)
│   ├── 2025/
│   │   └── 2025-06/
│   │       └── 2025-06-04/
│   │           └── 2025-06-04-153000-DJI-Mavic3Pro-24mm.jpg
├── videos/             # All video files (for use with DaVinci Resolve)
    ├── 2025/
    │   └── 2025-06/
    │       └── 2025-06-04/
    │           └── 2025-06-04-153000-4K-60p-01m24s-DJI-Mavic3Pro.mp4
```

This separation allows you to:

1. Point Luminar Neo directly to the `photos` directory without seeing any video files
2. Point DaVinci Resolve to the `videos` directory for your video editing workflow
3. Maintain timestamp-based organization within each media type

## Project Structure

```text
preprocess-input-media/
├── process_media.py    # Main command-line entry point
├── src/
│   ├── core/           # Core system components
│   ├── processors/     # File type specific processors
│   ├── sources/        # Source specific handlers
│   └── utils/          # Utility functions for file handling, timestamps, etc.
├── tests/              # Test suite
│   └── data/           # Test data files
├── samples/            # Sample files from different sources
├── venv/               # Virtual environment
├── requirements.txt    # Project dependencies
└── README.md           # This file
```

## License

MIT License

## Live command line example

```bash
cd preprocess-input-media
source venv/bin/activate                                     
python3 process_media.py -i /path/to/input/directory -o /path/to/output/directory --remove-processed
```

## Test run example command

```bash
source venv/bin/activate && python process_media.py --input samples --output output --dry-run
```
