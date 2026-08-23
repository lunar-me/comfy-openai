import httpx


class ComfyError(Exception):
    """Raised when ComfyUI returns an error response."""


class ComfyClient:
    """Thin async client for the ComfyUI HTTP API."""

    def __init__(self, base_url: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def queue_prompt(self, workflow: dict, client_id: str) -> str:
        """Submit a workflow to ComfyUI and return its prompt_id."""
        payload = {"prompt": workflow, "client_id": client_id}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/prompt", json=payload
            )
        if response.status_code >= 400:
            raise ComfyError(f"ComfyUI rejected prompt: {response.text}")
        data = response.json()
        prompt_id = data.get("prompt_id")
        if not prompt_id:
            raise ComfyError(f"ComfyUI returned no prompt_id: {data}")
        return prompt_id

    async def get_history(self, prompt_id: str) -> dict:
        """Fetch the execution history entry for a prompt_id."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/history/{prompt_id}"
            )
        response.raise_for_status()
        return response.json()

    async def get_image(self, filename: str, subfolder: str = "", type: str = "output") -> bytes:
        """Retrieve a generated image's raw bytes from ComfyUI."""
        params = {"filename": filename, "subfolder": subfolder, "type": type}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/view", params=params
            )
        response.raise_for_status()
        return response.content
