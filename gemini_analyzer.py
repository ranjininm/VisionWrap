import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from PIL import Image, ImageOps


# =========================================================
# CONFIGURATION
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

# Prefer the project's .env configuration.
load_dotenv(BASE_DIR / ".env", override=True)

API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

MODEL_NAME = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash"
).strip()

if not API_KEY:
    raise ValueError(
        "GEMINI_API_KEY was not found. "
        "Add it to the .env file beside app.py."
    )

client = genai.Client(api_key=API_KEY)


# =========================================================
# ANALYSIS PROMPT
# =========================================================

ANALYSIS_PROMPT = """
You are VisionWrap, an AI-powered product identification and
packaging recommendation system.

Analyze the main physical product in the supplied image.

Return exactly one valid JSON object. Do not use Markdown.

Use this schema:

{
  "product_name": "specific product name or Unknown product",
  "product_category": "electronics | electronics_accessory | fragile_item | clothing | book | household_item | cosmetic | food_container | toy | other",
  "confidence": "high | medium | low",
  "visible_material": "visible material or unknown",
  "description": "short description of the visible object",
  "fragility": "potentially_fragile | potentially_durable | unknown",
  "risk_factors": [],
  "estimated_size_class": "small | medium | large | unknown",
  "dimensions_cm": null,
  "weight_g": null,
  "packaging": {
    "recommended_box": "mailer box | corrugated cardboard box | rigid box | padded mailer | custom-fit box | other",
    "outer_material": "recommended packaging material",
    "cushioning": "recommended cushioning",
    "void_fill": "recommended void-fill or none",
    "orientation": "recommended orientation or handling",
    "protection_features": [],
    "reasoning": "brief explanation",
    "sustainability_tip": "practical waste-reduction suggestion"
  },
  "packing_steps": [],
  "warnings": [],
  "needs_confirmation": true
}

RULES:

1. Identify the main physical product, not the background.
2. Examine the shape, visible features and context before naming it.
3. Be cautious with visually similar products.
4. Use Unknown product and low confidence when identification
   is genuinely unclear.
5. Never invent exact dimensions, weight or material composition.
6. Dimensions and weight must remain null unless reliable
   measurements are explicitly provided.
7. Treat size as a rough visual estimate only.
8. Treat fragility as a potential packaging risk, not a
   confirmed physical test result.
9. Recommend anti-static protection for electronics where appropriate.
10. Recommend sufficient cushioning for potentially fragile items.
11. Prevent movement inside the package.
12. Avoid oversized rigid boxes for soft goods.
13. Prefer recyclable materials where suitable.
14. Do not invent exact box dimensions.
15. Provide practical packing steps.
16. Explain uncertainty in warnings.
17. Set needs_confirmation to true when important details
    are uncertain.
18. Return only the JSON object.
"""


# =========================================================
# IMAGE PROCESSING
# =========================================================

def normalise_image(image_input):
    """Convert supported image inputs into a standard RGB image."""

    if isinstance(image_input, Image.Image):
        image = image_input.copy()

    elif isinstance(image_input, (str, Path)):
        with Image.open(image_input) as source:
            image = source.copy()

    elif hasattr(image_input, "read"):
        if hasattr(image_input, "seek"):
            image_input.seek(0)

        with Image.open(image_input) as source:
            image = source.copy()

    else:
        raise TypeError(
            "Provide an image path, PIL Image, or uploaded image."
        )

    image = ImageOps.exif_transpose(image)
    image = image.convert("RGB")
    image.thumbnail((1600, 1600))

    return image


# =========================================================
# JSON PROCESSING
# =========================================================

def extract_json(response_text):
    if not response_text:
        raise ValueError("Gemini returned an empty response.")

    text = response_text.strip()

    text = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = re.sub(r"\s*```\s*$", "", text)

    try:
        result = json.loads(text)

    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)

        if not match:
            raise ValueError(
                "Gemini did not return valid JSON. Please retry."
            )

        result = json.loads(match.group(0))

    if not isinstance(result, dict):
        raise ValueError("Unexpected response format from Gemini.")

    return result


def normalise_result(result):
    defaults = {
        "product_name": "Unknown product",
        "product_category": "other",
        "confidence": "low",
        "visible_material": "unknown",
        "description": "No description available.",
        "fragility": "unknown",
        "risk_factors": [],
        "estimated_size_class": "unknown",
        "dimensions_cm": None,
        "weight_g": None,
        "packaging": {},
        "packing_steps": [],
        "warnings": [],
        "needs_confirmation": True,
    }

    for key, default in defaults.items():
        if key not in result or result[key] is None:
            result[key] = default

    if not isinstance(result["packaging"], dict):
        result["packaging"] = {}

    packaging_defaults = {
        "recommended_box": "Not determined",
        "outer_material": "Not determined",
        "cushioning": "Not determined",
        "void_fill": "Not determined",
        "orientation": "Not determined",
        "protection_features": [],
        "reasoning": "No explanation available.",
        "sustainability_tip": (
            "Use appropriately sized recyclable packaging where suitable."
        ),
    }

    for key, default in packaging_defaults.items():
        if (
            key not in result["packaging"]
            or result["packaging"][key] is None
        ):
            result["packaging"][key] = default

    for key in ("risk_factors", "packing_steps", "warnings"):
        value = result.get(key)

        if isinstance(value, str):
            result[key] = [value]
        elif not isinstance(value, list):
            result[key] = []

    features = result["packaging"].get("protection_features")

    if isinstance(features, str):
        result["packaging"]["protection_features"] = [features]
    elif not isinstance(features, list):
        result["packaging"]["protection_features"] = []

    return result


# =========================================================
# GEMINI ANALYZER
# =========================================================

class GeminiProductAnalyzer:
    """Identify a product and recommend suitable packaging."""

    def __init__(self, model_name=None):
        self.model_name = model_name or MODEL_NAME

    def analyze_image(self, image_input):
        image = normalise_image(image_input)

        last_error = None

        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=[
                        ANALYSIS_PROMPT,
                        image,
                    ],
                    config={
                        "response_mime_type": "application/json",
                    },
                )

                response_text = getattr(response, "text", None)

                result = extract_json(response_text)

                return normalise_result(result)

            except Exception as error:
                last_error = error
                message = str(error).upper()

                temporary = any(
                    marker in message
                    for marker in (
                        "503",
                        "UNAVAILABLE",
                        "429",
                        "RESOURCE_EXHAUSTED",
                        "500",
                        "INTERNAL",
                        "502",
                        "504",
                        "TIMEOUT",
                    )
                )

                if temporary and attempt < 2:
                    time.sleep(2 ** (attempt + 1))
                    continue

                if temporary:
                    raise RuntimeError(
                        "Gemini is temporarily unavailable or the "
                        "request quota may be exhausted. Try again later. "
                        f"Details: {error}"
                    ) from error

                raise RuntimeError(
                    "Product analysis failed. Check your model name, "
                    "API key configuration, network and API access. "
                    f"Details: {error}"
                ) from error

        raise RuntimeError(
            f"Gemini analysis failed: {last_error}"
        )
