import pytest

from rocksynth.assets import scan_rocks, scan_surfaces


def test_directory_scan_needs_no_metadata_or_manifest(tmp_path):
    for name in ("b", "a"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "01.blend").touch()
    assert [p.relative_to(tmp_path).as_posix() for p in scan_rocks(tmp_path)] == ["a/01.blend", "b/01.blend"]


def test_surface_channels_and_ambiguous_maps(tmp_path):
    folder = tmp_path / "sand"
    folder.mkdir()
    (folder / "basecolor.png").touch()
    (folder / "normal.exr").touch()
    assert set(scan_surfaces(tmp_path)[0]) == {"basecolor", "normal"}
    (folder / "basecolor.jpg").touch()
    with pytest.raises(ValueError, match="Multiple basecolor"):
        scan_surfaces(tmp_path)


def test_missing_assets_report_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match=str(tmp_path)):
        scan_rocks(tmp_path)
    folder = tmp_path / "broken"
    folder.mkdir()
    with pytest.raises(ValueError, match="Missing basecolor"):
        scan_surfaces(tmp_path)
