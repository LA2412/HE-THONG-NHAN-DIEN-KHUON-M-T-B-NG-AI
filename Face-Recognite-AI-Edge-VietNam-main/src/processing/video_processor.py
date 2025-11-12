"""
Module to process a video file and extract face embeddings.
"""

import cv2
import numpy as np
import sys
import os

# Add project root to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.recognition import Regconizer

def process_video(video_path: str, sample_rate: int = 2) -> np.ndarray:
    """
    Processes a video file, samples frames, detects faces, and returns embeddings.

    Args:
        video_path (str): Path to the video file.
        sample_rate (int): Number of frames to process per second.

    Returns:
        np.ndarray: A numpy array of face embeddings, shape (N, D). Returns an empty array if no faces are found.
    """
    if not os.path.exists(video_path):
        print(f"Error: Video file not found at {video_path}")
        return np.array([])

    rec = Regconizer()
    cam = cv2.VideoCapture(video_path)
    if not cam.isOpened():
        print(f"Error: Could not open video file {video_path}")
        return np.array([])

    fps = cam.get(cv2.CAP_PROP_FPS)
    if fps == 0:
        print("Warning: Could not get video FPS. Defaulting to 60.")
        fps = 60

    frame_interval = int(fps / sample_rate)
    if frame_interval == 0:
        frame_interval = 1

    embeddings_buffer = []
    frame_count = 0
    processed_count = 0

    print(f"Processing video '{os.path.basename(video_path)}'...")

    while True:
        ret, frame = cam.read()
        if not ret:
            break

        if frame_count % frame_interval == 0:
            # Process this frame
            embeddings = rec.get_face_embedding(frame)
            if len(embeddings) == 1:
                embeddings_buffer.append(embeddings[0])
                processed_count += 1
                print(f"  - Found face in frame {frame_count}. Total faces collected: {processed_count}")
            elif len(embeddings) > 1:
                print(f"  - Warning: Multiple faces detected in frame {frame_count}. Skipping.")
            # else: no face found, do nothing

        frame_count += 1

    cam.release()

    if not embeddings_buffer:
        print("No valid faces found in the video.")
        return np.array([])

    print(f"Video processing complete. Extracted {len(embeddings_buffer)} embeddings.")
    return np.array(embeddings_buffer)
