import os

_DEFAULT_IMAGE_PROMPT = """\
This image is being converted to text so it can be included in a markdown document. \
Your output replaces the image entirely — a reader will never see the original.

Produce the best text replacement:
- Readable text, tables, or handwriting → transcribe verbatim in markdown.
- Charts or graphs → state the type, axes, and key data points.
- Diagrams or flowcharts → list the components and their relationships.
- Photographs or illustrations → describe what is shown so a reader understands the content.

Output only the replacement text. No preamble.\
"""

IMAGE = os.environ.get("CAPTIONING_PROMPT", _DEFAULT_IMAGE_PROMPT)
