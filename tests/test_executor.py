from app.comfy.executor import ComfyExecutor, _video_ext, _video_format


def _executor() -> ComfyExecutor:
    """Build an executor instance without needing a real ComfyClient."""
    return ComfyExecutor.__new__(ComfyExecutor)  # type: ignore[call-arg]


def test_video_format_normalization():
    assert _video_format("mp4") == "mp4"
    assert _video_format("video/h264-mp4") == "mp4"
    assert _video_format("WEBM") == "webm"
    assert _video_format("png") is None
    assert _video_format("") is None
    assert _video_format(None) is None


def test_video_ext_falls_back_to_filename_extension():
    # No "format" field — detected from the filename extension.
    assert _video_ext({"filename": "clip.mp4"}) == "mp4"
    assert _video_ext({"filename": "clip.webm"}) == "webm"
    # A real image is not a video.
    assert _video_ext({"filename": "clip.png"}) is None
    # Explicit (mime-ish) format wins over filename.
    assert _video_ext({"filename": "clip.mp4", "format": "video/h264-mp4"}) == "mp4"


def test_extract_videos_from_gifs_key():
    history = {
        "outputs": {
            "92": {
                "gifs": [
                    {
                        "filename": "a.mp4",
                        "subfolder": "",
                        "type": "output",
                        "format": "mp4",
                    }
                ]
            }
        }
    }
    videos = _executor()._extract_videos(history, "p")
    assert len(videos) == 1
    assert videos[0].filename == "a.mp4"
    assert videos[0].format == "mp4"


def test_extract_videos_from_images_key_with_video_format():
    """Built-in SaveVideo may report the video under 'images' with a video format."""
    history = {
        "outputs": {
            "92": {
                "images": [
                    {
                        "filename": "a.mp4",
                        "subfolder": "",
                        "type": "output",
                        "format": "video/h264-mp4",
                    }
                ]
            }
        }
    }
    videos = _executor()._extract_videos(history, "p")
    assert len(videos) == 1
    assert videos[0].filename == "a.mp4"
    assert videos[0].format == "mp4"  # normalized from video/h264-mp4

    # The same entry must NOT be treated as an image.
    images = _executor()._extract_images(history, "p")
    assert images == []


def test_extract_images_keeps_real_images():
    history = {
        "outputs": {
            "9": {
                "images": [
                    {"filename": "a.png", "subfolder": "", "type": "output", "format": "png"}
                ]
            }
        }
    }
    images = _executor()._extract_images(history, "p")
    assert len(images) == 1
    assert images[0].filename == "a.png"
