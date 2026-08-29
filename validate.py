# This isn't how I would maintain/manage python code, but is intended to show 
# a minimum example of how you could use python to validate `predefined_url.json`
# Cheers!
# - ZH
"""Validate the JSON has valid URLs"""

import json
from pathlib import Path
import sys
# Because I saw you're using 3.10, we use this. If 3.11+, use 'from typing import Self'
from typing_extensions import Self
from pydantic import BaseModel, HttpUrl

class PredefinedUrl(BaseModel):
    """Predefined URL Entry"""
    url: HttpUrl



    @classmethod
    def from_file(cls, file: Path) -> list[Self]:
        """Load a list of predefined URLs from file"""
        with file.open("r", encoding="utf8") as handle:
            data: list[dict[str, str]] = json.load(handle)
        return [cls.model_validate(x) for x in data]

def main() -> None:
    """Program main entry point"""
    predefined_url = Path(sys.argv[1])
    if not predefined_url.is_file():
        raise FileNotFoundError(f"Could not find {predefined_url=}")
    model = PredefinedUrl.from_file(predefined_url)
    print(f"Model is valid: {model=}")


if __name__ == "__main__": # pragma: no cover
    main()