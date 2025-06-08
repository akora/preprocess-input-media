"""
Core file processor module for media pre-processing system.

This module handles the general processing flow for all media types.
"""

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.utils.metadata_extractor import MetadataExtractor
from src.utils.file_utils import (
    get_file_extension,
    get_normalized_extension,
    create_output_directory,
    is_file_already_processed
)
from src.utils.timestamp_utils import (
    extract_timestamp_from_metadata,
    extract_timestamp_from_filename,
    get_formatted_timestamp
)
from src.config import DEVICE_PATTERNS, FILENAME_PATTERNS


class FileProcessor:
    """Base processor for all media files."""

    def __init__(self, input_path: str, output_base_dir: str, timezone: str = 'local'):
        """
        Initialize the file processor.
        
        Args:
            input_path: Path to the input file
            output_base_dir: Base directory for processed outputs
            timezone: Timezone to use for timestamps (default: system local timezone)
        """
        self.input_path = Path(input_path)
        self.output_base_dir = Path(output_base_dir)
        self.timezone = timezone
        self.metadata_extractor = MetadataExtractor()
        self.metadata = {}
        self.device_type = None
        self.media_type = None
        
    def process(self) -> Optional[str]:
        """
        Process the file. This is the main method that orchestrates the processing flow.
        
        Returns:
            Path to the processed file or None if processing was skipped or failed
        """
        if not self.input_path.exists():
            print(f"Error: Input file does not exist: {self.input_path}")
            return None
        
        # Extract metadata
        self.metadata = self.metadata_extractor.extract_metadata(str(self.input_path))
        if not self.metadata:
            print(f"Error: Could not extract metadata from {self.input_path}")
            return None
        
        # Identify device type and media type
        self.device_type = self._identify_device_type()
        self.media_type = self._identify_media_type()
        
        if not self.device_type or not self.media_type:
            print(f"Warning: Could not identify device or media type for {self.input_path}")
            return None
        
        # Log which file we're processing
        print(f"Processing file: {self.input_path.name}")
        
        # Special handling for Sony files which have date issues
        is_sony_arw = self.input_path.suffix.lower() == '.arw'
        is_sony_mp4 = self.input_path.suffix.lower() == '.mp4' and self.input_path.name.startswith('C')
        
        # Print a special message for Sony ARW files which have special handling
        if is_sony_arw:
            print(f"Processing Sony ARW file: {self.input_path.name}")
        
        # For detailed debugging, uncomment this section
        # if is_sony_arw or is_sony_mp4:
        #     # Print metadata structure details
        #     pass
        
        # Extract timestamp using a hybrid approach for best accuracy
        filename_timestamp = extract_timestamp_from_filename(self.input_path.name)
        
        # Direct timestamp extraction for Sony files
        sony_timestamp = None
        
        if is_sony_arw or is_sony_mp4:
            # Import dateutil here as we're using it directly
            import dateutil.parser
            from datetime import datetime, timezone
            
            if is_sony_arw:
                # For Sony ARW files (DSC*.ARW)
                # Process Sony ARW file timestamps
                
                # Try Composite:SubSecDateTimeOriginal first (most accurate with subseconds and timezone)
                if 'Composite' in self.metadata and 'SubSecDateTimeOriginal' in self.metadata['Composite']:
                    try:
                        date_str = self.metadata['Composite']['SubSecDateTimeOriginal']
                        # Special handling for Sony date format (YYYY:MM:DD HH:MM:SS.sss+TZ)
                        # First, handle the colon-separated date part properly
                        if ':' in date_str and date_str.count(':') >= 2:
                            date_parts = date_str.split(' ', 1)
                            if len(date_parts) == 2:
                                date_part = date_parts[0].replace(':', '-')
                                time_part = date_parts[1]
                                # Reconstruct the date string with standard format
                                date_str = f"{date_part} {time_part}"
                        
                        sony_timestamp = dateutil.parser.parse(date_str)
                    except Exception as e:
                        print(f"Error parsing Composite:SubSecDateTimeOriginal: {e}")
                        
                # Next try System:FileModifyDate which has original capture time with timezone
                if not sony_timestamp and 'System' in self.metadata and 'FileModifyDate' in self.metadata['System']:
                    try:
                        date_str = self.metadata['System']['FileModifyDate']
                        # Handle colon-separated date format
                        if ':' in date_str and date_str.count(':') >= 2:
                            date_parts = date_str.split(' ', 1)
                            if len(date_parts) == 2:
                                date_part = date_parts[0].replace(':', '-')
                                time_part = date_parts[1]
                                date_str = f"{date_part} {time_part}"
                        
                        sony_timestamp = dateutil.parser.parse(date_str)
                    except Exception as e:
                        print(f"Error parsing System:FileModifyDate: {e}")
                
                # Try ExifIFD:DateTimeOriginal combined with OffsetTimeOriginal
                if not sony_timestamp and 'ExifIFD' in self.metadata:
                    if 'DateTimeOriginal' in self.metadata['ExifIFD']:
                        date_str = self.metadata['ExifIFD']['DateTimeOriginal']
                        # Get timezone if available
                        tz_offset = None
                        if 'OffsetTimeOriginal' in self.metadata['ExifIFD']:
                            tz_offset = self.metadata['ExifIFD']['OffsetTimeOriginal']
                        
                        try:
                            # Handle colon-separated date format
                            if ':' in date_str and date_str.count(':') >= 2:
                                date_parts = date_str.split(' ', 1)
                                if len(date_parts) == 2:
                                    date_part = date_parts[0].replace(':', '-')
                                    time_part = date_parts[1]
                                    date_str = f"{date_part} {time_part}"
                            
                            sony_timestamp = dateutil.parser.parse(f"{date_str}{tz_offset if tz_offset else ''}")
                        except Exception as e:
                            print(f"Error parsing ExifIFD:DateTimeOriginal: {e}")
                
                # Try IFD0:ModifyDate as last resort for ARW files
                if not sony_timestamp and 'IFD0' in self.metadata and 'ModifyDate' in self.metadata['IFD0']:
                    try:
                        date_str = self.metadata['IFD0']['ModifyDate']
                        # Handle colon-separated date format
                        if ':' in date_str and date_str.count(':') >= 2:
                            date_parts = date_str.split(' ', 1)
                            if len(date_parts) == 2:
                                date_part = date_parts[0].replace(':', '-')
                                time_part = date_parts[1]
                                date_str = f"{date_part} {time_part}"
                        
                        sony_timestamp = dateutil.parser.parse(date_str)
                    except Exception as e:
                        print(f"Error parsing IFD0:ModifyDate: {e}")
            
            elif is_sony_mp4:
                # For Sony MP4 files (C*.MP4)
                
                # First, try XML:CreationDateValue which contains the correct timestamp with timezone
                if 'XML' in self.metadata and 'CreationDateValue' in self.metadata['XML']:
                    date_str = self.metadata['XML']['CreationDateValue']
                    print(f"Found XML:CreationDateValue: {date_str}")
                    
                    try:
                        # Format the date string correctly first
                        # Convert YYYY:MM:DD to YYYY-MM-DD while preserving the time and timezone
                        parts = date_str.split(' ')
                        if len(parts) >= 2:
                            date_part = parts[0].replace(':', '-')
                            time_part = ' '.join(parts[1:])
                            formatted_date_str = f"{date_part} {time_part}"
                            print(f"Formatted XML date string: {formatted_date_str}")
                            
                            # Parse the formatted date string
                            sony_timestamp = dateutil.parser.parse(formatted_date_str)
                            print(f"Parsed Sony timestamp from XML:CreationDateValue: {sony_timestamp}")
                    except Exception as e:
                        print(f"Error parsing XML:CreationDateValue: {e}")
                        sony_timestamp = None
                
                # If XML:CreationDateValue failed, fall back to QuickTime:CreateDate
                if not sony_timestamp and 'QuickTime' in self.metadata and 'CreateDate' in self.metadata['QuickTime']:
                    date_str = self.metadata['QuickTime']['CreateDate']
                    # Replace colons in date with dashes for standard format
                    # Format is typically YYYY:MM:DD HH:MM:SS
                    if ':' in date_str:
                        parts = date_str.split(' ')
                        if len(parts) >= 2:
                            # Replace colons with dashes only in the date part
                            date_part = parts[0].replace(':', '-')
                            # Keep the time part as is
                            time_part = ' '.join(parts[1:])
                            date_str = f"{date_part} {time_part}"
                        print(f"Formatted date string: {date_str}")
                    
                    # Get timezone if available
                    tz_offset = None
                    if 'QuickTime' in self.metadata and 'TimeZone' in self.metadata['QuickTime']:
                        tz_offset = self.metadata['QuickTime']['TimeZone']
                    
                    try:
                        # Parse QuickTime:CreateDate with timezone if available
                        try:
                            # Standard parsing should work now with our reformatted date string
                            sony_timestamp = dateutil.parser.parse(f"{date_str}{tz_offset if tz_offset else ''}")
                            
                            print(f"Parsed Sony timestamp from QuickTime:CreateDate: {sony_timestamp}")
                        except ValueError:
                            # Fallback to manual parsing if needed
                            print("Falling back to manual timestamp parsing")
                            try:
                                # Try to extract components from the date string
                                date_parts = date_str.split(' ')
                                if len(date_parts) >= 2:
                                    ymd_parts = date_parts[0].split('-')
                                    hms_parts = date_parts[1].split(':')
                                    
                                    if len(ymd_parts) >= 3 and len(hms_parts) >= 3:
                                        year = int(ymd_parts[0])
                                        month = int(ymd_parts[1])
                                        day = int(ymd_parts[2])
                                        hour = int(hms_parts[0])
                                        minute = int(hms_parts[1])
                                        second = int(float(hms_parts[2]))
                                        
                                        # Create datetime manually
                                        dt = datetime(year, month, day, hour, minute, second)
                                        
                                        # Add timezone if available
                                        if tz_offset:
                                            dt = dt.replace(tzinfo=timezone(dateutil.parser.parse(f"2000-01-01 12:00:00{tz_offset}").utcoffset()))
                                        
                                        sony_timestamp = dt
                                        
                                        print(f"Manually parsed timestamp: {sony_timestamp}")
                            except Exception as e:
                                print(f"Error in manual parsing: {e}")
                        # This section is now handled in the try block above
                    except Exception as e:
                        print(f"Error parsing QuickTime:CreateDate: {e}")
                
                # If that failed, try System:FileModifyDate as fallback
                if not sony_timestamp and 'System' in self.metadata and 'FileModifyDate' in self.metadata['System']:
                    try:
                        print(f"Using System:FileModifyDate for MP4: {self.metadata['System']['FileModifyDate']}")
                        sony_timestamp = dateutil.parser.parse(self.metadata['System']['FileModifyDate'])
                    except Exception as e:
                        print(f"Error parsing System:FileModifyDate: {e}")
                        
                # Next try XML:LastUpdate
                if not sony_timestamp and 'XML' in self.metadata and 'LastUpdate' in self.metadata['XML']:
                    try:
                        print(f"Using XML:LastUpdate: {self.metadata['XML']['LastUpdate']}")
                        sony_timestamp = dateutil.parser.parse(self.metadata['XML']['LastUpdate'])
                    except Exception as e:
                        print(f"Error parsing XML:LastUpdate: {e}")
        
        # Extract timestamp using standard methods as fallback
        filename_timestamp = extract_timestamp_from_filename(self.input_path.name)
        metadata_timestamp = sony_timestamp if sony_timestamp else extract_timestamp_from_metadata(self.metadata, self.timezone)
        
        # For debugging
        print(f"  Filename timestamp: {filename_timestamp}")
        print(f"  Metadata timestamp: {metadata_timestamp}")
        
        # For Sony files, prefer metadata timestamp since filenames don't have dates
        # For other files (DJI, screen recordings), prefer filename timestamp if available
        if is_sony_arw or is_sony_mp4:
            # Use sony_timestamp if available, otherwise fall back to metadata_timestamp
            timestamp = sony_timestamp if sony_timestamp else metadata_timestamp
            print(f"  Using timestamp from Sony metadata: {timestamp}")
            # Add extra metadata diagnostic for ARW files
            if is_sony_arw:
                print(f"  ARW file: sony_timestamp={sony_timestamp}, metadata_timestamp={metadata_timestamp}")
        else:
            # For non-Sony files, prefer filename timestamp if available
            timestamp = filename_timestamp if filename_timestamp else metadata_timestamp
        
        if not timestamp:
            print(f"Warning: Could not extract timestamp from {self.input_path}")
            return None
        
        # Format timestamp for output path
        date_str, time_str = get_formatted_timestamp(timestamp)
        
        # Create output directory structure with media type separation
        output_dir = create_output_directory(self.output_base_dir, timestamp, self.media_type)
        
        # Generate new filename
        new_filename = self._generate_new_filename(date_str, time_str)
        if not new_filename:
            print(f"Warning: Could not generate new filename for {self.input_path}")
            return None
        
        # Create output path
        output_path = output_dir / new_filename
        # Check if already processed
        if is_file_already_processed(str(self.input_path), str(output_path)):
            print(f"Skipping already processed file: {self.input_path}")
            return None
        try:
            # Copy the file to the output directory
            shutil.copy2(self.input_path, output_path)
            print(f"Processed: {self.input_path} -> {output_path}")
            return str(output_path)
        except Exception as e:
            print(f"Error processing {self.input_path}: {str(e)}")
            return None

    def _identify_device_type(self) -> Optional[str]:
        """
        Identify the device type based on filename and metadata.
        
        Returns:
            Device type identifier or None if not identified
        """
        filename = self.input_path.name
        file_ext = self.input_path.suffix.lower()
        
        # Special handling for Sony MP4 files with C prefix (e.g., C0001.MP4)
        if file_ext == '.mp4' and filename[0] == 'C':
            # Check if the rest of the name is only digits (ignoring file extension)
            base_name = filename.split('.')[0]
            if base_name[1:].isdigit():
                # Even if there's no specific metadata, assume Sony camera for this naming pattern
                # This is based on Sony's typical file naming for video clips
                return 'sony_camera'
                
        # Special handling for already processed files with device name in the filename
        if 'DJI-Mavic3Pro' in filename:
            return 'dji_drone'
        elif 'DJI-RCPro' in filename:
            return 'dji_rc_pro'
        elif 'Sony-ILCE' in filename:
            return 'sony_camera'
        
        # Check regular patterns
        for device, patterns in DEVICE_PATTERNS.items():
            # Check filename patterns
            for pattern in patterns.get('filename_patterns', []):
                if pattern in filename:
                    return device
            
            # Check metadata patterns (case insensitive)
            for field, values in patterns.get('metadata_patterns', {}).items():
                # Try both original case and lowercase field names in metadata
                metadata_value = self.metadata.get(field)
                if not metadata_value:
                    metadata_value = self.metadata.get(field.lower())
                
                if metadata_value:
                    for value in values:
                        if isinstance(metadata_value, str) and value.lower() in metadata_value.lower():
                            return device
        
        # Last resort: try to identify by file extension and naming convention
        if self.input_path.suffix.lower() in ['.arw']:
            return 'sony_camera'
        elif self.input_path.suffix.lower() in ['.dng', '.jpg', '.jpeg', '.mp4'] and ('DJI' in filename or 'FC43' in filename):
            return 'dji_drone'
        elif self.input_path.suffix.lower() in ['.mp4'] and ('Sony' in filename or 'ILCE' in filename):
            return 'sony_camera'
        
        return None
    
    def _identify_media_type(self) -> Optional[str]:
        """
        Identify the media type (image or video) based on file extension.
        
        Returns:
            Media type identifier ('image', 'video') or None if not identified
        """
        ext = get_file_extension(self.input_path).lower()
        
        if ext in ['.jpg', '.jpeg', '.dng', '.arw']:
            return 'image'
        elif ext in ['.mp4']:
            return 'video'
        
        return None
    
    def _generate_new_filename(self, date_str: str, time_str: str) -> Optional[str]:
        """
        Generate new filename based on device type, media type, and metadata.
        
        Args:
            date_str: Formatted date string
            time_str: Formatted time string
        
        Returns:
            New filename or None if generation failed
        """
        # Get file extension
        ext = get_normalized_extension(get_file_extension(self.input_path))
        
        # Get device-specific identification information
        make = self._extract_make()
        model = self._extract_model()
        
        # Clean up make and model to avoid spaces in filenames
        if make:
            # Replace spaces with dashes in make
            make = make.replace(' ', '-')
            
        if model:
            # Convert specific models with spaces to camelCase or dash format
            if 'RC Pro' in model:
                model = 'RCPro'  # camelCase for RC Pro
            elif 'Mavic 3 Pro' in model:
                model = 'Mavic3Pro'  # camelCase for Mavic 3 Pro
            elif 'ILCE-' in model:
                # For Sony ILCE cameras, remove the dash after ILCE
                model = model.replace('ILCE-', 'ILCE')
                # Also replace any remaining spaces with dashes
                model = model.replace(' ', '-')
            else:
                # For other models, just replace spaces with dashes
                model = model.replace(' ', '-')
        
        # Generate device specific components based on patterns in config
        components = {
            'datetime': f"{date_str}-{time_str}",
            'date': date_str,
            'time': time_str,
            'make': make,
            'model': model,
            'ext': ext
        }
        
        # Add device-specific components
        if self.device_type == 'dji_drone':
            seq_num = self._extract_sequence_number()
            if seq_num:
                components['sequence'] = seq_num
                
            # Add drone model name (always Mavic3Pro for now)
            components['model'] = 'Mavic3Pro'
                
            # Add focal length for all DJI drone photos
            if self.media_type == 'image':
                focal_length = self._extract_focal_length()
                if focal_length:
                    components['focal_length'] = focal_length
        
        # Add media-specific components
        if self.media_type == 'video':
            resolution = self._extract_resolution()
            if resolution:
                components['resolution'] = resolution
            
            fps = self._extract_fps()
            if fps:
                components['fps'] = fps
                
            # Add video duration in human-readable format
            duration = self._extract_video_duration()
            if duration:
                components['duration'] = duration
                
        elif self.media_type == 'image' and self.device_type == 'sony_camera':
            # Add shutter count for Sony cameras
            shutter_count = self._extract_shutter_count()
            if shutter_count:
                components['shutter_count'] = shutter_count
        
        # Get filename pattern for this device + media type
        pattern = FILENAME_PATTERNS.get(
            (self.device_type, self.media_type),
            FILENAME_PATTERNS.get('default')
        )
        
        # Fill in the pattern
        try:
            # Replace each {key} with its value
            new_filename = pattern
            for key, value in components.items():
                if value is not None:
                    placeholder = '{' + key + '}'
                    if placeholder in new_filename:
                        new_filename = new_filename.replace(placeholder, str(value))
            
            # Clean up any unused placeholders
            import re
            new_filename = re.sub(r'\{[^\}]+\}', '', new_filename)
            new_filename = new_filename.replace('--', '-')
            
            # Final check for any remaining spaces
            new_filename = new_filename.replace(' ', '-')
            
            return new_filename
        except Exception as e:
            print(f"Error generating filename: {e}")
            return None
    
    def _extract_make(self) -> str:
        """Extract the make/manufacturer from metadata."""
        # Try different metadata fields in order of preference
        make_fields = ['Make', 'DeviceManufacturer', 'manufacturer']
        
        for field in make_fields:
            make = self.metadata.get(field)
            if make and isinstance(make, str) and make.strip():
                return make.strip()
        
        # Special handling for specific devices
        if self.device_type == 'dji_rc_pro':
            return 'DJI'
        elif self.device_type == 'dji_drone':
            return 'DJI'
        elif self.device_type == 'sony_camera':
            return 'Sony'
        
        return 'Unknown'  # Never return empty string
    
    def _extract_model(self) -> str:
        """Extract the model from metadata."""
        # Try different metadata fields in order of preference
        model_fields = ['Model', 'DeviceModelName', 'modelname']
        
        for field in model_fields:
            model = self.metadata.get(field)
            if model and isinstance(model, str) and model.strip():
                return model.strip()
        
        # If still empty, use device type info
        if self.device_type == 'dji_drone':
            return 'Mavic 3 Pro'
        elif self.device_type == 'sony_camera':
            return 'ILCE-7M4'
        elif self.device_type == 'dji_rc_pro':
            return 'RC Pro'
            
        return 'Unknown'  # Never return empty string
    
    def _extract_sequence_number(self) -> Optional[str]:
        """Extract sequence number from filename for DJI drone files."""
        if self.device_type == 'dji_drone':
            filename = self.input_path.name
            # Extract sequence number from DJI_YYYYMMDDHHMMSS_XXXX_D format
            parts = filename.split('_')
            if len(parts) >= 3:
                return parts[2]
        
        return None
    
    def _extract_shutter_count(self) -> Optional[str]:
        """Extract shutter count for Sony cameras."""
        if self.device_type == 'sony_camera':
            # Try to get from ShutterCount metadata
            shutter_count = self.metadata.get('ShutterCount')
            if shutter_count:
                try:
                    return f"{int(str(shutter_count).strip()):06d}"
                except (ValueError, TypeError):
                    pass
                
            # Try to get from ShutterCount2 metadata
            shutter_count = self.metadata.get('ShutterCount2')
            if shutter_count:
                try:
                    return f"{int(str(shutter_count)):06d}"
                except (ValueError, TypeError):
                    pass
        
        return None
    
    def _extract_resolution(self) -> Optional[str]:
        """Extract resolution for video files."""
        # Check if this is a Sony MP4 file with typical fields
        if self.device_type == 'sony_camera' and self.input_path.suffix.lower() == '.mp4':
            # Try Sony-specific fields first
            width = self.metadata.get('VideoFormatVideoLayoutPixel')
            height = self.metadata.get('VideoFormatVideoLayoutNumOfVerticalLine')
            
            # If we have both width and height as valid numbers
            if width and height:
                try:
                    width = int(width)
                    height = int(height)
                    if height == 2160:
                        return '4K'
                    elif height == 1080:
                        return 'FHD'
                    elif height == 720:
                        return 'HD'
                    else:
                        return f"{height}p"
                except (ValueError, TypeError):
                    pass
        
        # General approach for all files
        resolution_fields = [
            # Standard fields
            ('ImageWidth', 'ImageHeight'),
            # Sony MP4 specific fields
            ('VideoFormatVideoLayoutPixel', 'VideoFormatVideoLayoutNumOfVerticalLine'),
            # Other possible fields
            ('Width', 'Height'),
            ('SourceImageWidth', 'SourceImageHeight'),
            # Group-prefixed fields
            ('XML:VideoFormatVideoLayoutPixel', 'XML:VideoFormatVideoLayoutNumOfVerticalLine'),
            ('Composite:ImageWidth', 'Composite:ImageHeight')
        ]
        
        # Try fields in order of preference
        for width_field, height_field in resolution_fields:
            try:
                width = self.metadata.get(width_field)
                height = self.metadata.get(height_field)
                
                if width and height:
                    # Try to extract numeric values if they're strings
                    if isinstance(width, str):
                        try:
                            width = int(width.split('x')[0].strip())
                        except (ValueError, IndexError):
                            continue
                    
                    if isinstance(height, str):
                        try:
                            height = int(height.split('x')[1].strip() if 'x' in height else height)
                        except (ValueError, IndexError):
                            continue
                    
                    # Get standardized resolution name
                    if height == 2160:
                        return '4K'
                    elif height == 1080:
                        return 'FHD'
                    elif height == 720:
                        return 'HD'
                    else:
                        return f"{height}p"
            except (KeyError, TypeError, ValueError):
                continue
        
        # Check for ImageSize field (like "3840x2160" or "3840 2160")
        image_size = self.metadata.get('ImageSize')
        if image_size and isinstance(image_size, str):
            # Handle both "3840x2160" and "3840 2160" formats
            separator = 'x' if 'x' in image_size else ' '
            if separator in image_size:
                try:
                    width, height = map(int, image_size.lower().split(separator))
                    if height == 2160:
                        return '4K'
                    elif height == 1080:
                        return 'FHD'
                    elif height == 720:
                        return 'HD'
                    else:
                        return f"{height}p"
                except (ValueError, IndexError):
                    pass
        
        return None
    
    def _extract_fps(self) -> Optional[str]:
        """Extract FPS (frames per second) information for video files."""
        # Special handling for Sony MP4 files
        if self.device_type == 'sony_camera' and self.input_path.suffix.lower() == '.mp4':
            # First try Sony-specific fields
            for field in ['VideoFormatVideoFrameCaptureFps', 'VideoFormatVideoFrameFormatFps', 'XML:VideoFormatVideoFrameCaptureFps']:
                value = self.metadata.get(field)
                if value:
                    # Handle Sony FPS formats like '25.00p' or '25p'
                    try:
                        value_str = str(value)
                        if 'p' in value_str:
                            fps = float(value_str.split('p')[0])
                            if abs(fps - 24) < 0.5:
                                return '24p'
                            elif abs(fps - 25) < 0.5:
                                return '25p'
                            elif abs(fps - 30) < 0.5:
                                return '30p'
                            elif abs(fps - 50) < 0.5:
                                return '50p'
                            elif abs(fps - 60) < 0.5:
                                return '60p'
                            else:
                                return f"{int(fps)}p" if fps.is_integer() else f"{fps:.2f}p"
                    except (ValueError, TypeError):
                        pass
        
        # Generic approach for all files
        fps_fields = [
            'VideoFrameRate', 
            'VideoFrameRateManual',
            'VideoFormatVideoFrameCaptureFps',
            'VideoFormatVideoFrameFormatFps',
            'FrameRate',
            'XML:VideoFormatVideoFrameCaptureFps',
            'XML:VideoFormatVideoFrameFormatFps',
            'XML:LtcChangeTableTcFps',
            'AvgFrameRate'
        ]

        # Try to get FPS from any of the fields
        for field in fps_fields:
            try:
                value = self.metadata.get(field)
                if not value:
                    continue
                    
                # Convert to string for consistent processing
                value_str = str(value)
                
                # Try to extract numeric part
                try:
                    # Handle different formats like '24', '24p', '24.00p'
                    if 'p' in value_str:
                        fps = float(value_str.split('p')[0])
                    else:
                        fps = float(value_str)
                    
                    # Standardize popular framerates
                    if abs(fps - 24) < 0.5:
                        return '24p'
                    elif abs(fps - 25) < 0.5:
                        return '25p'
                    elif abs(fps - 30) < 0.5:
                        return '30p'
                    elif abs(fps - 50) < 0.5:
                        return '50p'
                    elif abs(fps - 60) < 0.5:
                        return '60p'
                    else:
                        return f"{int(fps)}p" if fps.is_integer() else f"{fps:.2f}p"
                except (ValueError, TypeError):
                    continue
            except Exception:
                continue
        
        return None
        
    def _extract_video_duration(self) -> Optional[str]:
        """Extract video duration in a human-readable format (e.g., 2m34s)."""
        if self.media_type != 'video':
            return None
            
        # Fields that might contain duration information
        duration_fields = [
            'Duration',
            'MediaDuration',
            'TrackDuration',
            'QuickTime:Duration',
            'XML:Duration',
            'MediaCreateDate',
            'MediaModifyDate',
            'TrackCreateDate',
            'TrackModifyDate'
        ]
        
        # Try to extract duration in seconds
        duration_seconds = None
        
        # First try direct duration fields
        for field in duration_fields:
            value = self.metadata.get(field)
            if not value:
                continue
                
            try:
                # Handle different formats
                value_str = str(value)
                
                # Format like "0:02:34" (h:mm:ss)
                if ':' in value_str and value_str.count(':') >= 1:
                    parts = value_str.split(':')
                    if len(parts) == 3:  # hh:mm:ss
                        h, m, s = map(float, parts)
                        duration_seconds = h * 3600 + m * 60 + s
                    elif len(parts) == 2:  # mm:ss
                        m, s = map(float, parts)
                        duration_seconds = m * 60 + s
                        
                # Format like "2.5 s" or just "2.5"
                elif 's' in value_str or value_str.replace('.', '').isdigit():
                    # Extract numeric part
                    numeric_part = ''.join(c for c in value_str if c.isdigit() or c == '.')
                    try:
                        duration_seconds = float(numeric_part)
                    except ValueError:
                        continue
                        
                if duration_seconds is not None:
                    break
            except Exception:
                continue
                
        # If we found duration in seconds, format it nicely
        if duration_seconds is not None:
            # Convert to minutes and seconds
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            
            # Format as "02m34s" or just "34s" if less than a minute
            if minutes > 0:
                return f"{minutes:02d}m{seconds:02d}s"
            else:
                return f"{seconds:02d}s"
                
        return None

    def _extract_focal_length(self) -> Optional[str]:
        """Extract focal length information for DJI Mavic 3 Pro photos."""
        if self.media_type != 'image' or self.device_type != 'dji_drone':
            return None
            
        # Get filename, camera model and lens ID from metadata
        filename = self.input_path.name.lower()
        camera_model = str(self.metadata.get('Model', '')).lower()
        lens_id = str(self.metadata.get('LensID', '')).lower()
        
        # Map camera codes to focal lengths
        if 'l2d-20c' in filename or 'l2d-20c' in camera_model or 'l2d-20c' in lens_id:
            return '24mm'  # Wide angle lens (24mm equivalent)
        elif 'fc4382' in filename or 'fc4382' in camera_model or 'fc4382' in lens_id:
            return '70mm'  # Telephoto lens (70mm equivalent)
        elif 'fc4370' in filename or 'fc4370' in camera_model or 'fc4370' in lens_id:
            return '166mm'  # Super telephoto lens (166mm equivalent)
            
        return None
