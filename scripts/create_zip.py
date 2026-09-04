#!/usr/bin/env python3
"""
Packages the entire codebase and report files into a clean submission zip archive.
"""

import os
import zipfile

def make_submission_zip():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    zip_filename = os.path.abspath(os.path.join(base_dir, "..", "llm_assisted_robomaster.zip"))

    print(f"Creating submission zip: {zip_filename}")
    print(f"Source directory: {base_dir}")

    exclude_patterns = [
        "__pycache__", ".pytest_cache", ".git", ".vscode",
        ".DS_Store", "*.pyc", "*.pyo", "build", "install", "log"
    ]

    count = 0
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(base_dir):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_patterns and not d.startswith('.')]

            for file in files:
                if any(file.endswith(ext.replace("*", "")) for ext in [".pyc", ".pyo", ".zip"]):
                    continue
                if file.startswith("."):
                    continue

                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir)
                archive_name = os.path.join("llm_robot_task_planning", rel_path)
                zipf.write(full_path, archive_name)
                count += 1

    print(f"[SUCCESS] Packaged {count} files into '{zip_filename}' successfully.")
    return zip_filename

if __name__ == "__main__":
    make_submission_zip()
