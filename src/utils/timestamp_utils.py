"""
Timestamp utility functions for media pre-processing.

This module provides utility functions for extracting and handling timestamps
from files and metadata.
"""

import os
import re
import dateutil.parser
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

from dateutil.tz import tzlocal


def extract_timestamp_from_metadata(metadata: Dict[str, Any], 
                                    timezone_str: str = 'local') -> Optional[datetime]:
    """
    Extract the timestamp from file metadata.
    
    This function tries several metadata fields to find the creation timestamp.
    Handles both flat and nested metadata structures (like Sony ARW files).
    
    Args:
        metadata: Dictionary of file metadata
        timezone_str: Timezone to use ('local' for system timezone or a TZ identifier)
        
    Returns:
        Datetime object or None if no timestamp could be extracted
    """
    # Fields to check for timestamp in order of preference
    timestamp_fields = [
        # Sony-specific fields (high priority)
        'ExifIFD:DateTimeOriginal',  # For Sony ARW files
        'IFD0:ModifyDate',           # For Sony ARW files
        'System:FileModifyDate',      # System file date as fallback
        
        # QuickTime fields for Sony MP4 files (high priority)
        'QuickTime:CreateDate',
        'Track1:TrackCreateDate',
        
        # Composite fields (often have timezone information)
        'SubSecDateTimeOriginal',
        'SubSecCreateDate',
        'SubSecModifyDate',
        
        # EXIF fields
        'DateTimeOriginal',
        'CreateDate',
        'ModifyDate',
        
        # Group-prefixed metadata fields
        'EXIF:DateTimeOriginal',
        'EXIF:CreateDate',
        'EXIF:ModifyDate',
        'Composite:SubSecDateTimeOriginal',
        'Composite:SubSecCreateDate',
        'Composite:SubSecModifyDate',
        
        # QuickTime fields for MP4 files
        'QuickTime:MediaCreateDate',
        'QuickTime:TrackCreateDate',
        'QuickTime:ModifyDate',
        
        # XML fields (often in Sony MP4 files)
        'XML:CreationDate',
        'XML:LastUpdate',
        
        # File modification fields
        'FileModifyDate',
        'File:FileModifyDate',
        
        # Video-specific fields
        'MediaCreateDate',
        'TrackCreateDate',
        
        # Other potential fields
        'CreationDateValue',
        'CreationTime'
    ]
    
    # Get timezone
    if timezone_str == 'local':
        tz = tzlocal()
    else:
        try:
            tz = timezone.gettz(timezone_str)
            if tz is None:
                tz = tzlocal()
        except:
            tz = tzlocal()
    
    # Combine all metadata fields from nested dictionaries
    flat_metadata = {}
    _flatten_metadata(metadata, flat_metadata)
    
    # Debug: print top-level keys to understand the structure
    # print(f"Metadata top-level keys: {list(metadata.keys())}")
    
    # Special handling for Sony MP4 files (C0001.MP4, etc.)
    if 'QuickTime' in metadata:
        # Add QuickTime timestamps directly to flat_metadata for easier access
        quicktime_data = metadata['QuickTime']
        # print(f"QuickTime keys: {list(quicktime_data.keys())}")
        
        # Add all QuickTime fields to flat metadata with proper timezone
        for qt_field in ['CreateDate', 'ModifyDate', 'TrackCreateDate', 'MediaCreateDate']:
            if qt_field in quicktime_data:
                # Try to combine with timezone from QuickTime if available
                timezone_str = None
                if 'TimeZone' in quicktime_data and isinstance(quicktime_data['TimeZone'], str):
                    timezone_str = quicktime_data['TimeZone']
                    qt_value = f"{quicktime_data[qt_field]}{timezone_str}"
                else:
                    qt_value = quicktime_data[qt_field]
                
                # Add with QuickTime prefix
                flat_metadata[f'QuickTime:{qt_field}'] = qt_value
                
                # Also add without prefix for better matching
                if qt_field not in flat_metadata:
                    flat_metadata[qt_field] = qt_value
    
    # Try each timestamp field
    for field in timestamp_fields:
        # Look in flattened metadata first
        timestamp_str = flat_metadata.get(field, metadata.get(field))
        if not timestamp_str or not isinstance(timestamp_str, str):
            continue
        
        try:
            # Try to parse the timestamp
            dt = dateutil.parser.parse(timestamp_str, fuzzy=True)
            
            # Handle timezone
            if dt.tzinfo is None:
                # Check for separate timezone fields that might apply
                offset_fields = ['OffsetTimeOriginal', 'OffsetTime', 'TimeZoneOffset', 
                               'EXIF:OffsetTimeOriginal', 'EXIF:OffsetTime']
                for offset_field in offset_fields:
                    offset = flat_metadata.get(offset_field, metadata.get(offset_field))
                    if offset and isinstance(offset, str):
                        try:
                            # Try to parse "+02:00" type offsets
                            offset_hours = int(offset[1:3])
                            offset_mins = int(offset[4:]) if len(offset) > 4 else 0
                            
                            offset_seconds = offset_hours * 3600 + offset_mins * 60
                            if offset[0] == '+':
                                tzinfo = timezone(timedelta(seconds=offset_seconds))
                            else:
                                tzinfo = timezone(timedelta(seconds=-offset_seconds))
                                
                            dt = dt.replace(tzinfo=tzinfo)
                            break
                        except (ValueError, IndexError):
                            pass
                
                # If still no timezone, use the specified one
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tz)
            else:
                # If timezone in string but we want local, convert it
                if timezone_str == 'local':
                    dt = dt.astimezone(tz)
            
            return dt
        except (ValueError, TypeError):
            continue
    
    # If we couldn't find any valid timestamp, try file modification date as last resort
    if 'File' in metadata and isinstance(metadata['File'], dict) and 'FileModifyDate' in metadata['File']:
        try:
            dt = dateutil.parser.parse(metadata['File']['FileModifyDate'], fuzzy=True)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return dt
        except (ValueError, TypeError):
            pass
    
    return None
    
def _flatten_metadata(metadata: Dict[str, Any], result: Dict[str, Any], prefix: str = '') -> None:
    """
    Recursively flatten nested metadata dictionaries.
    
    Args:
        metadata: The metadata dictionary to flatten
        result: Dictionary to store flattened results
        prefix: Prefix for nested keys
    """
    if not isinstance(metadata, dict):
        return
        
    for key, value in metadata.items():
        new_key = f"{prefix}:{key}" if prefix else key
        if isinstance(value, dict):
            # Recurse into nested dict
            _flatten_metadata(value, result, new_key)
            # Also add this dict's keys directly in case they're useful
            for k, v in value.items():
                if not isinstance(v, dict):
                    flat_key = f"{new_key}:{k}"
                    result[flat_key] = v
        else:
            # Add the value with its full path key
            result[new_key] = value


def extract_timestamp_from_filename(filename: str) -> Optional[datetime]:
    """
    Extract timestamp from common filename patterns.
    
    This function supports several patterns:
    - DJI_YYYYMMDDHHMMSS_* (DJI drone files)
    - *_YYYYMMDDHHMMSS_* (generic timestamp format)
    - screen-YYYYMMDD-HHMMSS* (DJI RC Pro screen recordings)
    - DSCXXXXX (fallback to file stats for Sony files)
    
    Args:
        filename: Filename to extract timestamp from
        
    Returns:
        Datetime object or None if no timestamp could be extracted
    """
    # Try DJI format: DJI_YYYYMMDDHHMMSS_*
    dji_pattern = r'DJI_(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})_'
    match = re.search(dji_pattern, filename)
    if match:
        try:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second, tzinfo=tzlocal())
        except (ValueError, TypeError):
            pass
    
    # Try screen recording format: screen-YYYYMMDD-HHMMSS*
    screen_pattern = r'screen-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})'
    match = re.search(screen_pattern, filename)
    if match:
        try:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second, tzinfo=tzlocal())
        except (ValueError, TypeError):
            pass
    
    # Try generic format with Date_Time pattern
    generic_pattern = r'(\d{4})[-_]?(\d{2})[-_]?(\d{2})[-_T]?(\d{2})[-_:]?(\d{2})[-_:]?(\d{2})'
    match = re.search(generic_pattern, filename)
    if match:
        try:
            year, month, day, hour, minute, second = map(int, match.groups())
            return datetime(year, month, day, hour, minute, second, tzinfo=tzlocal())
        except (ValueError, TypeError):
            pass
    
    return None


def get_formatted_timestamp(timestamp: datetime) -> Tuple[str, str]:
    """
    Format a timestamp into date and time strings.
    
    Args:
        timestamp: Datetime object to format
        
    Returns:
        Tuple of (date_string, time_string)
    """
    date_str = timestamp.strftime('%Y%m%d')
    time_str = timestamp.strftime('%H%M%S')
    return date_str, time_str


def normalize_timezone(dt: datetime, timezone_str: str = 'local') -> datetime:
    """
    Normalize a datetime to the specified timezone.
    
    Args:
        dt: Datetime object to normalize
        timezone_str: Timezone to normalize to ('local' for system timezone)
        
    Returns:
        Datetime object in the specified timezone
    """
    # Get target timezone
    if timezone_str == 'local':
        target_tz = tzlocal()
    else:
        try:
            target_tz = timezone.gettz(timezone_str)
            if target_tz is None:
                target_tz = tzlocal()
        except:
            target_tz = tzlocal()
    
    # If datetime has no timezone, assume local
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tzlocal())
    
    # Convert to target timezone
    return dt.astimezone(target_tz)
