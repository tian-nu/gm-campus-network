"""Shared Windows utilities."""

import subprocess
import sys
from typing import List


def run_hidden_command(args: List[str], timeout: int = 5):
    """Run a Windows shell command without flashing a console window.

    Output is decoded with fallback encodings for Chinese Windows (gbk/cp936).
    """
    kwargs: dict = {
        "capture_output": True,
        "timeout": timeout,
    }
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW

    try:
        result = subprocess.run(args, **kwargs)
    except subprocess.TimeoutExpired:
        raise TimeoutError(f"Command timed out: {' '.join(args)}")
    except Exception as e:
        raise RuntimeError(f"Command failed: {e}") from e

    for stream_name in ("stdout", "stderr"):
        raw_value = getattr(result, stream_name)
        if isinstance(raw_value, bytes):
            decoded_value = ""
            for encoding in ("utf-8", "gbk", "cp936", "mbcs"):
                try:
                    decoded_value = raw_value.decode(encoding)
                    break
                except Exception:
                    continue
            else:
                decoded_value = raw_value.decode("utf-8", errors="replace")
            setattr(result, stream_name, decoded_value)
    return result
