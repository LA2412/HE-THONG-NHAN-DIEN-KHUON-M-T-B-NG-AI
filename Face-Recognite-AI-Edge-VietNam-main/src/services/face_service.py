"""
High level utilities for managing face embeddings and raw assets.
"""

from __future__ import annotations

import os
from glob import glob
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from src.core.vectordb import VectorBD
from src.processing import image_processor, video_processor
from src.utils import add_id_name, check_is_id_exist, get_name_from_id, init_id_name
from legacy_scripts import create_database as legacy_builder


ROOT_DIR = Path(__file__).resolve().parents[2]
MEDIA_DIR = ROOT_DIR / "database" / "data"
VIDEO_DIR = MEDIA_DIR / "video"
IMAGE_DIR = MEDIA_DIR / "image"

VIDEO_DIR.mkdir(parents=True, exist_ok=True)
IMAGE_DIR.mkdir(parents=True, exist_ok=True)


def list_faces() -> List[Dict]:
    mapping = init_id_name()
    return [
        {"face_id": int(face_id), "name": name}
        for face_id, name in sorted(mapping.items(), key=lambda kv: int(kv[0]))
    ]


def next_face_id() -> int:
    mapping = init_id_name()
    if not mapping:
        return 1
    return max(int(face_id) for face_id in mapping.keys()) + 1


def _vector_db() -> VectorBD:
    return VectorBD()


def add_embeddings(face_id: int, name: str, embeddings: np.ndarray, is_update: bool = False) -> int:
    if embeddings.size == 0:
        raise ValueError("Không tìm thấy khuôn mặt hợp lệ trong dữ liệu nguồn.")
    db = _vector_db()
    if is_update and check_is_id_exist(face_id):
        db.add_more_emb(embeddings, face_id)
    else:
        db.add_emb(embeddings, name, face_id)
    return embeddings.shape[0]


def add_from_video(face_id: int, name: str, video_path: str, is_update: bool = False) -> int:
    embeddings = video_processor.process_video(video_path)
    return add_embeddings(face_id, name, embeddings, is_update=is_update)


def add_from_image_folder(face_id: int, name: str, folder_path: str, is_update: bool = False) -> int:
    embeddings = image_processor.process_image_folder(folder_path)
    return add_embeddings(face_id, name, embeddings, is_update=is_update)


def remove_face(face_id: int) -> None:
    name = get_name_from_id(face_id)
    if not name:
        raise ValueError("ID không tồn tại trong cơ sở dữ liệu.")
    db = _vector_db()
    db.remove_emb(face_id, name)


def rename_face(face_id: int, new_name: str) -> None:
    if not check_is_id_exist(face_id):
        raise ValueError("Face ID không tồn tại.")
    old_name = get_name_from_id(face_id)
    if not old_name or old_name == new_name:
        return
    add_id_name(face_id, new_name)
    # Rename raw media folders to keep them consistent
    for base_dir in (VIDEO_DIR, IMAGE_DIR):
        for folder in base_dir.glob(f"{face_id}_*"):
            target = base_dir / f"{face_id}_{new_name}"
            if folder.exists() and folder != target:
                if target.exists():
                    # Merge contents if target already exists
                    for item in folder.iterdir():
                        dest = target / item.name
                        if dest.exists():
                            dest.unlink()
                        item.rename(dest)
                    folder.rmdir()
                else:
                    folder.rename(target)


def media_destination(face_id: int, name: str, media_type: str, extension: str) -> Path:
    base_dir = VIDEO_DIR if media_type == "video" else IMAGE_DIR
    safe_name = name.replace(" ", "_")
    folder = base_dir / f"{face_id}_{safe_name}"
    folder.mkdir(parents=True, exist_ok=True)
    version = 1
    extension = extension.lstrip(".")
    while True:
        candidate = folder / f"{face_id}_{safe_name}_L{version}.{extension}"
        if not candidate.exists():
            return candidate
        version += 1


def merge_profiles(primary_face_id: int, duplicate_face_id: int) -> Tuple[int, int]:
    """Merge duplicate embeddings into one profile and remove the duplicate."""
    if primary_face_id == duplicate_face_id:
        raise ValueError("Primary và duplicate phải khác nhau.")

    primary_name = get_name_from_id(primary_face_id)
    duplicate_name = get_name_from_id(duplicate_face_id)
    if not primary_name or not duplicate_name:
        raise ValueError("Không tìm thấy thông tin tên cho một trong các Face ID.")

    total_embeddings = 0
    duplicate_media_dirs: List[Path] = []
    for base_dir in (VIDEO_DIR, IMAGE_DIR):
        duplicate_path = base_dir / f"{duplicate_face_id}_{duplicate_name}"
        if duplicate_path.exists():
            duplicate_media_dirs.append(duplicate_path)

    for media_dir in duplicate_media_dirs:
        if media_dir.is_dir():
            if media_dir.parent.name == "video":
                video_files = glob(str(media_dir / "*.mp4"))
                for video in video_files:
                    total_embeddings += add_from_video(primary_face_id, primary_name, video, is_update=True)
            else:
                total_embeddings += add_from_image_folder(primary_face_id, primary_name, str(media_dir), is_update=True)

    remove_face(duplicate_face_id)
    return total_embeddings, duplicate_face_id


def rebuild_from_folder(root_folder: str, reinit: bool = True) -> None:
    legacy_builder.add_emb_in_folder(root_folder=root_folder, is_reinit=reinit)
