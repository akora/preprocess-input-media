"""
Main module for the media pre-processing system.

This module provides the entry point for the command line interface
and orchestrates the processing of media files.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Tuple

from src.core.file_processor import FileProcessor
from src.utils.file_utils import get_file_extension, initialize_processed_files_db, mark_file_as_processed
from src.utils.timestamp_utils import extract_timestamp_from_metadata, extract_timestamp_from_filename, get_formatted_timestamp
from src.config import (
    DEFAULT_INPUT_DIR,
    DEFAULT_OUTPUT_DIR,
    SUPPORTED_EXTENSIONS,
    PROCESSED_FILES_DB
)


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Pre-process media files from various sources.'
    )
    
    parser.add_argument(
        '--input', '-i',
        type=str,
        default=DEFAULT_INPUT_DIR,
        help=f'Input directory containing media files (default: {DEFAULT_INPUT_DIR})'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default=DEFAULT_OUTPUT_DIR,
        help=f'Output directory for processed files (default: {DEFAULT_OUTPUT_DIR})'
    )
    
    parser.add_argument(
        '--timezone', '-tz',
        type=str,
        default='local',
        help='Timezone to use for timestamps (default: system local timezone)'
    )
    
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively process files in subdirectories'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually processing files'
    )
    
    parser.add_argument(
        '--remove-processed',
        action='store_true',
        help='Remove successfully processed files from the input directory'
    )
    
    return parser.parse_args()


def find_media_files(input_dir: str, recursive: bool = False) -> List[Path]:
    """
    Find all supported media files in the input directory.
    
    Args:
        input_dir: Input directory to search
        recursive: Whether to search recursively in subdirectories
    
    Returns:
        List of Path objects for supported media files
    """
    input_path = Path(input_dir)
    if not input_path.exists():
        print(f"Error: Input directory '{input_dir}' does not exist.")
        return []
    
    # Get all extensions as a flat list
    all_extensions = []
    for ext_list in SUPPORTED_EXTENSIONS.values():
        all_extensions.extend(ext_list)
    
    # Find all files with supported extensions
    media_files = []
    
    if recursive:
        # Walk through all subdirectories
        for root, _, files in os.walk(input_dir):
            for filename in files:
                file_path = Path(root) / filename
                if get_file_extension(file_path).lower() in all_extensions:
                    media_files.append(file_path)
    else:
        # Only search in the top-level directory
        for item in input_path.iterdir():
            if item.is_file() and get_file_extension(item).lower() in all_extensions:
                media_files.append(item)
    
    return media_files


def process_files(
    media_files: List[Path],
    output_dir: str,
    timezone: str = 'local',
    dry_run: bool = False,
    remove_processed: bool = False
) -> Tuple[int, int]:
    """
    Process a list of media files.
    
    Args:
        media_files: List of media files to process
        output_dir: Output directory for processed files
        timezone: Timezone to use for timestamps
        dry_run: If True, only show what would be done
        remove_processed: If True, remove successfully processed files from input directory
    
    Returns:
        Tuple of (success_count, error_count)
    """
    # Initialize counts
    success_count = 0
    error_count = 0
    
    # Initialize the processed files database if not in dry-run mode
    if not dry_run:
        initialize_processed_files_db(PROCESSED_FILES_DB)
    
    # Process each file
    for file_path in media_files:
        print(f"{'[DRY RUN] ' if dry_run else ''}Processing: {file_path}")
        
        try:
            # Create file processor
            processor = FileProcessor(str(file_path), output_dir, timezone)
            
            if dry_run:
                # Just show what would be done
                metadata = processor.metadata_extractor.extract_metadata(str(file_path))
                device_type = processor._identify_device_type()
                media_type = processor._identify_media_type()
                
                # Extract timestamp for output path generation
                filename_timestamp = extract_timestamp_from_filename(file_path.name)
                metadata_timestamp = extract_timestamp_from_metadata(metadata, timezone)
                
                # Choose the appropriate timestamp based on device type
                if device_type == 'sony_camera':
                    timestamp = metadata_timestamp
                else:
                    timestamp = filename_timestamp if filename_timestamp else metadata_timestamp
                
                print(f"  Would process as: {device_type} {media_type}")
                print(f"  Metadata found: {', '.join(list(metadata.keys())[:5])}...")
                
                # Generate proposed output path if timestamp is available
                if timestamp:
                    date_str, time_str = get_formatted_timestamp(timestamp)
                    
                    # Create output directory structure with media type separation
                    base_output_dir = Path(output_dir)
                    # Add media type to path
                    if media_type == 'image':
                        media_output_dir = base_output_dir / 'photos'
                    elif media_type == 'video':
                        media_output_dir = base_output_dir / 'videos'
                    else:
                        media_output_dir = base_output_dir
                    
                    year_month = timestamp.strftime('%Y/%m')
                    proposed_output_dir = media_output_dir / year_month
                    
                    # Create processor to generate filename
                    processor.metadata = metadata
                    processor.device_type = device_type
                    processor.media_type = media_type
                    
                    # Print focal length information for DJI drone images
                    if device_type == 'dji_drone' and media_type == 'image':
                        model = processor._extract_model()
                        focal_length = processor._extract_focal_length()
                        print(f"  DJI Image - Model: {model}, Focal Length: {focal_length}")
                        
                        # Debug filename and metadata for focal length detection
                        filename = file_path.name.lower()
                        camera_model = str(metadata.get('Model', '')).lower()
                        lens_id = str(metadata.get('LensID', '')).lower()
                        print(f"  Debug - Filename: {filename}, Camera Model: {camera_model}, Lens ID: {lens_id}")
                    
                    # Generate new filename
                    new_filename = processor._generate_new_filename(date_str, time_str)
                    if new_filename:
                        proposed_output_path = proposed_output_dir / new_filename
                        print(f"  Would save to: {proposed_output_path}")
                    else:
                        print(f"  Could not generate output filename")
                else:
                    print(f"  Could not determine timestamp for output path")
                
                success_count += 1
            else:
                # Actually process the file
                output_path = processor.process()
                
                if output_path:
                    # Mark as processed
                    mark_file_as_processed(PROCESSED_FILES_DB, str(file_path), output_path)
                    success_count += 1
                    
                    # Remove the file if requested
                    if remove_processed:
                        try:
                            if dry_run:
                                print(f"  Would remove: {file_path}")
                            else:
                                os.remove(file_path)
                                print(f"  Removed: {file_path}")
                        except Exception as e:
                            print(f"  Error removing {file_path}: {str(e)}")
                else:
                    error_count += 1
                    
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
            error_count += 1
    
    return success_count, error_count


def main():
    """Main entry point for the application."""
    args = parse_arguments()
    
    print("Media File Pre-Processing System")
    print("===============================")
    print(f"Input directory: {args.input}")
    print(f"Output directory: {args.output}")
    print(f"Timezone: {args.timezone}")
    print(f"Recursive: {args.recursive}")
    print(f"Dry run: {args.dry_run}")
    print(f"Remove processed files: {args.remove_processed}")
    print("===============================")
    
    # Find media files
    media_files = find_media_files(args.input, args.recursive)
    
    if not media_files:
        print("No media files found in the input directory.")
        return
    
    print(f"Found {len(media_files)} media files to process.")
    
    # Process the files
    success_count, error_count = process_files(
        media_files, args.output, args.timezone, args.dry_run, args.remove_processed
    )
    
    print("===============================")
    print(f"Processing completed: {success_count} succeeded, {error_count} failed")
    
    return 0 if error_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
