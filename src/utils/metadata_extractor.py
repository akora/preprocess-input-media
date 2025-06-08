"""
Metadata extractor utility for media files.

This module handles extracting metadata from various media file types.
"""

import json
import os
import subprocess
from typing import Dict, Any, Optional


class MetadataExtractor:
    """Extract metadata from media files using exiftool."""
    
    def __init__(self):
        """Initialize the metadata extractor."""
        self._check_exiftool()
    
    def _check_exiftool(self) -> None:
        """Check if exiftool is installed and accessible."""
        try:
            subprocess.run(['exiftool', '-ver'], 
                          stdout=subprocess.PIPE, 
                          stderr=subprocess.PIPE, 
                          check=True)
        except (subprocess.SubprocessError, FileNotFoundError):
            raise RuntimeError(
                "exiftool not found. Please install exiftool before using this module."
            )
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from a file using ExifTool.
        
        Args:
            file_path: Path to file
            
        Returns:
            Dictionary of metadata or empty dict if extraction failed
        """
        try:
            # Run exiftool with JSON output and include hierarchical groups
            result = subprocess.run(
                ['exiftool', '-json', '-a', '-u', '-g1', file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            # Parse the JSON output
            try:
                metadata_list = json.loads(result.stdout)
                if metadata_list and isinstance(metadata_list, list):
                    # Get the metadata (first and usually only item in the list)
                    metadata = metadata_list[0]
                    
                    # Create a flattened version with both original hierarchical and flat keys
                    flattened_metadata = {}
                    
                    # Process all fields including nested ones
                    for group_key, group_data in metadata.items():
                        # Skip the SourceFile key
                        if group_key == 'SourceFile':
                            flattened_metadata[group_key] = group_data
                            continue
                            
                        # Handle group data (like QuickTime, XML, EXIF)
                        if isinstance(group_data, dict):
                            # Add the group itself
                            flattened_metadata[group_key] = group_data
                            
                            # Add all items in the group with prefixed keys (e.g., QuickTime:CreateDate)
                            for key, value in group_data.items():
                                prefixed_key = f"{group_key}:{key}"
                                flattened_metadata[prefixed_key] = value
                                
                                # Also add with no prefix for easier access
                                if key not in flattened_metadata:
                                    flattened_metadata[key] = value
                        else:
                            # Handle regular non-grouped metadata
                            flattened_metadata[group_key] = group_data
                    
                    return flattened_metadata
                return {}
            except json.JSONDecodeError:
                print(f"Error: Failed to parse exiftool output for {file_path}")
                return {}
                
        except subprocess.SubprocessError as e:
            print(f"Error running exiftool on {file_path}: {str(e)}")
            return {}
    
    def extract_specific_tags(self, file_path: str, tags: list) -> Dict[str, Any]:
        """
        Extract specific metadata tags from a media file.
        
        Args:
            file_path: Path to the media file
            tags: List of tags to extract
            
        Returns:
            Dictionary of metadata for the specified tags
        """
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return {}
        
        try:
            # Build the command with specific tags
            cmd = ['exiftool', '-json', '-a', '-u']
            for tag in tags:
                cmd.extend(['-' + tag])
            cmd.append(file_path)
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True
            )
            
            # Parse the JSON output
            try:
                metadata_list = json.loads(result.stdout)
                if metadata_list and isinstance(metadata_list, list):
                    return metadata_list[0]
                return {}
            except json.JSONDecodeError:
                print(f"Error: Failed to parse exiftool output for {file_path}")
                return {}
                
        except subprocess.SubprocessError as e:
            print(f"Error running exiftool on {file_path}: {str(e)}")
            return {}
            
    def get_creation_date(self, file_path: str) -> Optional[str]:
        """
        Get the creation date of a media file.
        
        This method tries several metadata fields to find the creation date.
        
        Args:
            file_path: Path to the media file
            
        Returns:
            Creation date string in format YYYY:MM:DD HH:MM:SS or None if not found
        """
        date_fields = [
            'DateTimeOriginal',
            'CreateDate',
            'MediaCreateDate',
            'TrackCreateDate',
            'ModifyDate',
            'FileModifyDate'
        ]
        
        metadata = self.extract_specific_tags(file_path, date_fields)
        
        for field in date_fields:
            date_str = metadata.get(field)
            if date_str and isinstance(date_str, str):
                # Extract the date part if it contains timezone info
                if '+' in date_str:
                    date_str = date_str.split('+')[0].strip()
                return date_str
                
        return None
