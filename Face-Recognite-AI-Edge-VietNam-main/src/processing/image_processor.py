"""
Module to process a folder of images and extract face embeddings.
"""

import cv2
import numpy as np
import sys
import os
from glob import glob

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.recognition import Regconizer
from src.utils import read_image

SUPPORTED_EXTENSIONS = ["*.jpg", "*.jpeg", "*.png"]

def process_image_folder(folder_path: str) -> np.ndarray:
    """
    Processes all images in a folder, detects faces, and returns embeddings.

    Args:
        folder_path (str): Path to the folder containing images.

    Returns:
        np.ndarray: A numpy array of face embeddings, shape (N, D). Returns an empty array if no faces are found.
    """
    if not os.path.isdir(folder_path):
        print(f"Error: Folder not found at {folder_path}")
        return np.array([])

    rec = Regconizer()
    image_paths = []
    for ext in SUPPORTED_EXTENSIONS:
        image_paths.extend(glob(os.path.join(folder_path, ext)))

    if not image_paths:
        print(f"No images found in {folder_path}")
        return np.array([])

    embeddings_buffer = []
    print(f"Processing {len(image_paths)} images in '{os.path.basename(folder_path)}'...")

    for i, img_path in enumerate(image_paths):
        try:
            image = read_image(img_path) # Use read_image from utils to handle BGR/RGB
            embeddings = rec.get_face_embedding(image)
            
            if len(embeddings) == 1:
                embeddings_buffer.append(embeddings[0])
                print(f"  - [{i+1}/{len(image_paths)}] Processed '{os.path.basename(img_path)}'. Face found.")
            elif len(embeddings) > 1:
                print(f"  - [{i+1}/{len(image_paths)}] Warning: Multiple faces detected in '{os.path.basename(img_path)}'. Skipping.")
            else:
                print(f"  - [{i+1}/{len(image_paths)}] Warning: No face detected in '{os.path.basename(img_path)}'. Skipping.")

        except Exception as e:
            print(f"  - Error processing image {img_path}: {e}")

    if not embeddings_buffer:
        print("No valid faces found in any of the images.")
        return np.array([])

    print(f"Image folder processing complete. Extracted {len(embeddings_buffer)} embeddings.")
    return np.array(embeddings_buffer)
