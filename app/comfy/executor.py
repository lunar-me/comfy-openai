import asyncio
import time

from app.comfy.client import ComfyClient, ComfyError


class ExecutionTimeoutError(Exception):
    """Raised when ComfyUI does not finish executing within the timeout."""


class OutputImage:
    """A generated image returned by ComfyUI."""

    def __init__(self, filename: str, subfolder: str = "", type: str = "output"):
        self.filename = filename
        self.subfolder = subfolder
        self.type = type


class ExecutionResult:
    """Result of a completed ComfyUI execution."""

    def __init__(self, images: list[OutputImage]):
        self.images = images


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

        if not images:
            raise ComfyError(
                f"ComfyUI completed but produced no images for {prompt_id}"
            )

        return ExecutionResult(images)

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
                images.append(
                    OutputImage(
                        filename=image["filename"],
                        subfolder=image.get("subfolder", ""),
                        type=image.get("type", "output"),
                    )
                )

        return images
