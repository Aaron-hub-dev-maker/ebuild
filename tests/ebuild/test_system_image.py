# SPDX-License-Identifier: MIT
# Copyright (c) 2026 EoS Project

"""Tests for ebuild.system.image.ImageBuilder.

No test here shells out to a real mkfs.ext4: subprocess.run is replaced
with a stub that answers a failure only for the mkfs.ext4 command and
delegates everything else (``_create_empty_image``'s ``dd``) to the real
implementation. That makes the failure path deterministic on any machine,
with or without e2fsprogs installed.
"""

import subprocess

import pytest

from ebuild.system.image import ImageBuilder, ImageError


def test_create_ext4_failure(tmp_path, monkeypatch):
    """A failing mkfs.ext4 must raise, not report a green image.

    Regression: ``_create_ext4`` ran mkfs.ext4 with ``capture_output=True``
    but never inspected the return code, so a disk-full or permission error
    left a corrupt ``.ext4`` on disk while the CLI printed
    "Image created: ..." and exited 0.
    """
    build_dir = tmp_path / "build"
    rootfs_dir = tmp_path / "rootfs"
    rootfs_dir.mkdir()

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "mkfs.ext4":
            return subprocess.CompletedProcess(
                cmd,
                returncode=1,
                stdout="",
                stderr="mkfs.ext4: Permission denied",
            )
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("ebuild.system.image.subprocess.run", fake_run)
    # The failure under test is mkfs's, not the tool being absent — and not
    # the host platform either, so the test is valid on Windows CI runners.
    monkeypatch.setattr("ebuild.system.image.IS_WINDOWS", False)
    monkeypatch.setattr("ebuild.system.image._has_command", lambda name: True)

    imager = ImageBuilder(build_dir)

    # Driven through create() rather than _create_ext4() directly, so the
    # output directory is created as it would be in a real `ebuild system`
    # run.
    with pytest.raises(ImageError, match="mkfs.ext4 failed") as excinfo:
        imager.create(
            rootfs_dir,
            image_format="ext4",
            image_size_mb=64,
            label="eos-rootfs",
        )

    assert "Permission denied" in str(excinfo.value)


def test_create_ext4_success(monkeypatch, tmp_path):
    """Ensure that a successful mkfs.ext4 execution completes without error."""
    build_dir = tmp_path / "build"
    fake_rootfs = tmp_path / "rootfs"
    fake_rootfs.mkdir()

    real_run = subprocess.run

    def fake_run(cmd, *args, **kwargs):
        if cmd and cmd[0] == "mkfs.ext4":
            return subprocess.CompletedProcess(
                cmd,
                returncode=0,
                stdout="Success",
                stderr=""
            )
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr("ebuild.system.image.subprocess.run", fake_run)
    monkeypatch.setattr("ebuild.system.image.IS_WINDOWS", False)
    monkeypatch.setattr("ebuild.system.image._has_command", lambda name: True)

    builder = ImageBuilder(build_dir)

    # create() should complete without raising ImageError
    output_file = builder.create(
        fake_rootfs,
        image_format="ext4",
        image_size_mb=64,
        label="eos-rootfs",
    )
    
    assert output_file is not None