import asyncio
import time

from app.comfy.client import ComfyClient, ComfyError

# Video container extensions that a history "format" string may denote.
VIDEO_FORMATS = {"mp4", "webm", "mov", "avi", "mkv", "gif"}


def _video_format(fmt) -> str | None:
    """Return a clean video extension for a history ``format`` value, or None.

    Handles plain extensions ("mp4") and mime-ish strings such as
    "video/h264-mp4" (-> "mp4"). Returns None when the value is not a video.
    """
    if not fmt:
        return None
    fmt = str(fmt).lower()
    if "/" in fmt:
        fmt = fmt.rsplit("/", 1)[-1]
    if "-" in fmt:
        fmt = fmt.rsplit("-", 1)[-1]
    return fmt if fmt in VIDEO_FORMATS else None


def _video_ext(entry: dict) -> str | None:
    """Return a clean video extension for a history output entry, or None.

    Uses the entry's ``format`` field first (plain or mime-ish), then falls
    back to the filename extension (e.g. "clip.mp4"). Returns None when the
    entry is not a video.
    """
    fmt = _video_format(entry.get("format", ""))
    if fmt:
        return fmt
    name = str(entry.get("filename", ""))
    if "." in name:
        ext = name.rsplit(".", 1)[-1].lower()
        if ext in VIDEO_FORMATS:
            return ext
    return None


class ExecutionTimeoutError(Exception):
    """Raised when ComfyUI does not finish executing within the timeout."""


class OutputImage:
    """A generated image returned by ComfyUI."""

    def __init__(self, filename: str, subfolder: str = "", type: str = "output"):
        self.filename = filename
        self.subfolder = subfolder
        self.type = type


class OutputVideo:
    """A generated video returned by ComfyUI (from a SaveVideo node)."""

    def __init__(
        self,
        filename: str,
        subfolder: str = "",
        type: str = "output",
        format: str = "mp4",
    ):
        self.filename = filename
        self.subfolder = subfolder
        self.type = type
        self.format = format


class ExecutionResult:
    """Result of a completed ComfyUI execution."""

    def __init__(self, images: list[OutputImage] | None = None, videos: list[OutputVideo] | None = None):
        self.images = images or []
        self.videos = videos or []


class ComfyExecutor:
    """Queues a workflow and waits (via polling) for the resulting images."""

    def __init__(
        self,
        client: ComfyClient,
        client_id: str = "comfy-openai",
        poll_interval: float = 0.5,
        timeout: float = 300.0,
    ):
        self.client = client
        self.client_id = client_id
        self.poll_interval = poll_interval
        self.timeout = timeout

    async def execute(self, workflow: dict) -> ExecutionResult:
        prompt_id = await self.client.queue_prompt(workflow, self.client_id)

        history = await self._wait_for_completion(prompt_id)

        images = self._extract_images(history, prompt_id)
        videos = self._extract_videos(history, prompt_id)

        if not images and not videos:
            raise ComfyError(
                f"ComfyUI completed but produced no output for {prompt_id}"
            )

        return ExecutionResult(images, videos)

    async def _wait_for_completion(self, prompt_id: str) -> dict:
        """Poll /history/{id} until the prompt's status is 'success' or timeout."""
        deadline = time.monotonic() + self.timeout

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ExecutionTimeoutError(
                    f"ComfyUI execution timed out after {self.timeout}s"
                )

            history = await self.client.get_history(prompt_id)
            entry = history.get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "success":
                    return entry
                if status.get("status_str") == "error":
                    raise ComfyError(f"ComfyUI execution error: {entry}")

            await asyncio.sleep(self.poll_interval)

    def _extract_images(self, history_entry: dict, prompt_id: str) -> list[OutputImage]:
        images: list[OutputImage] = []
        outputs = (history_entry or {}).get("outputs", {})

        for node_output in outputs.values():
            for image in node_output.get("images", []):
                # A video file may be reported under the "images" key with a
                # video format/extension — that belongs to _extract_videos.
                if _video_ext(image):
                    continue
                images.append(
                    OutputImage(
                        filename=image["filename"],
                        subfolder=image.get("subfolder", ""),
                        type=image.get("type", "output"),
                    )
                )

        return images

    def _extract_videos(self, history_entry: dict, prompt_id: str) -> list[OutputVideo]:
        """Collect videos reported by SaveVideo/CreateVideo nodes.

        Different ComfyUI video nodes report their output under different keys:
        VideoHelperSuite's SaveVideo uses ``outputs[].gifs``, some built-in
        nodes use ``outputs[].videos``, and others report the video file under
        ``outputs[].images`` with a video ``format``. We check all of these and
        normalize the format to a clean file extension.
        """
        videos: list[OutputVideo] = []
        outputs = (history_entry or {}).get("outputs", {})

        for node_output in outputs.values():
            for key in ("gifs", "videos"):
                for video in node_output.get(key, []):
                    videos.append(self._to_output_video(video))

            # Built-in SaveVideo may report the video under "images" too.
            for image in node_output.get("images", []):
                if _video_ext(image):
                    videos.append(self._to_output_video(image))

        return videos

    @staticmethod
    def _to_output_video(video: dict) -> OutputVideo:
        """Build an OutputVideo, normalizing the format to a clean extension."""
        return OutputVideo(
            filename=video["filename"],
            subfolder=video.get("subfolder", ""),
            type=video.get("type", "output"),
            format=_video_ext(video) or "mp4",
        )
