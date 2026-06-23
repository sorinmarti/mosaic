"""This module contains utility functions for working with files and directories."""

import shutil
from pathlib import Path


def delete_all_in_folder(folder_path):
    """This function deletes all files and folders in the specified directory."""
    # Convert to Path object
    folder = Path(folder_path)

    # Check if the folder exists
    if not folder.exists():
        return

    # Loop through each item in the directory
    for item_path in folder.iterdir():
        try:
            if item_path.is_file() or item_path.is_symlink():
                # If it's a file or symlink, delete it
                item_path.unlink()
            elif item_path.is_dir():
                # If it's a directory, delete it and all its contents
                shutil.rmtree(item_path)
        except Exception as e:
            print(f"Failed to delete {item_path}. Reason: {e}")
