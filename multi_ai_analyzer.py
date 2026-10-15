import base64
import json
import os
import re
from io import BytesIO
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

# =========================================================
# MODEL CONFIGURATION
# =========================================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.8-flash",
).strip()

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-5-mini",
).strip()

ANTHROPIC_MODEL = os.getenv(
    "ANTHROPIC_MODEL",
    "claude-haiku-4-5-20251001",
).strip()


# =========================================================
# COMMON PRODUCT ANALYSIS PROMPT
# =========================================================

ANALYSIS_PROMPT = """
You are VisionWrap, an AI product identification and
intelligent packaging recommendation system.

Analyze the main physical product visible in the supplied image.

Return exactly one valid JSON object.
Do not return Markdown or code fences.

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
    "outer_material": "recommended outer packaging material",
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

1. Identify the actual product, not its background.
2. Consider the object's visible shape and features.
3. If several products look similar, lower confidence.
4. If unclear, use Unknown product and low confidence.
5. Never invent exact dimensions or weight.
6. Keep dimensions_cm and weight_g null unless reliable
   measurements are explicitly provided.
7. Treat size as a rough visual estimate.
8. Assess potential fragility without claiming physical testing.
9. Recommend anti-static protection for suitable electronics.
10. Recommend cushioning and movement prevention for fragile items.
11. Avoid oversized boxes for soft goods.
12. Prefer recyclable materials when appropriate.
13. Do not invent exact box dimensions.
14. Keep packing steps practical and concise.
15. Explain important uncertainties in warnings.
16. Set needs_confirmation to true.
17. Return only valid JSON matching the schema.
"""


# =========================================================
# IMAGE NORMALIZATION
# =========================================================

def normalize_image(image_input):
    """Convert an image input into a standardized RGB PIL image."""

    if isinstance(image_input, Image.Image):
        image = image_input.copy()

    elif hasattr(image_input, "read"):
        if hasattr(image_input, "seek"):
            image_input.seek(0)

        with Image.open(image_input) as source:
            image = source.copy()

    elif isinstance(image_input, (str, Path)):
        with Image.open(image_input) as source:
            image = source.copy()

    else:
        raise TypeError(
            "Provide a PIL image, image path, or uploaded image."
        )

    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((1600, 1600))

    return image


def image_to_base64(image):
    """Encode the image as JPEG base64 for vision APIs."""

    buffer = BytesIO()

    image.save(
        buffer,
        format="JPEG",
        quality=90,
    )

    return base64.b64encode(buffer.getvalue()).decode("utf-8")


# =========================================================
# JSON PARSING AND RESULT NORMALIZATION
# =========================================================

def parse_json_response(text):
    """Extract a JSON object from an AI response."""

    if not text:
        raise ValueError("The AI provider returned an empty response.")

    text = text.strip()

    text = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(r"\s*```\s*$", "", text)

    try:
        result = json.loads(text)

    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)

        if not match:
            raise ValueError(
                "The AI provider did not return a valid JSON object."
            )

        result = json.loads(match.group(0))

    if not isinstance(result, dict):
        raise ValueError("The AI response must be a JSON object.")

    return normalize_result(result)


def normalize_result(result):
    """Ensure every provider returns fields expected by VisionWrap."""

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

    for key, value in defaults.items():
        if key not in result or result[key] is None:
            result[key] = value

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

    for key, value in packaging_defaults.items():
        if result["packaging"].get(key) is None:
            result["packaging"][key] = value

    list_fields = (
        "risk_factors",
        "packing_steps",
        "warnings",
    )

    for key in list_fields:
        value = result.get(key)

        if isinstance(value, str):
            result[key] = [value] if value.strip() else []

        elif not isinstance(value, list):
            result[key] = []

    features = result["packaging"].get("protection_features")

    if isinstance(features, str):
        result["packaging"]["protection_features"] = [features]

    elif not isinstance(features, list):
        result["packaging"]["protection_features"] = []

    return result


# =========================================================
# PROVIDER IMPLEMENTATIONS
# =========================================================

def analyze_with_gemini(image):
    """Use the existing Gemini analyzer."""

    from gemini_analyzer import GeminiProductAnalyzer

    analyzer = GeminiProductAnalyzer(
        model_name=GEMINI_MODEL,
    )

    result = analyzer.analyze_image(image)

    return normalize_result(result)


def analyze_with_openai(image):
    """Analyze an image using the OpenAI Responses API."""

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured."
        )

    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    encoded_image = image_to_base64(image)

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": ANALYSIS_PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": (
                            f"data:image/jpeg;base64,{encoded_image}"
                        ),
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    return parse_json_response(response.output_text)


def analyze_with_anthropic(image):
    """Analyze an image using the Anthropic Messages API."""

    api_key = os.getenv("ANTHROPIC_API_KEY")

    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not configured."
        )

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    encoded_image = image_to_base64(image)

    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1800,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": encoded_image,
                        },
                    },
                    {
                        "type": "text",
                        "text": ANALYSIS_PROMPT,
                    },
                ],
            }
        ],
    )

    text_parts = [
        block.text
        for block in response.content
        if getattr(block, "type", None) == "text"
    ]

    if not text_parts:
        raise ValueError(
            "Claude returned no text response."
        )

    return parse_json_response("\n".join(text_parts))


# =========================================================
# MULTI-AI FALLBACK ROUTER
# =========================================================

class MultiAIProductAnalyzer:
    """
    Provider order:
        1. Gemini
        2. OpenAI
        3. Anthropic Claude

    The first successful, valid analysis is returned.
    """

    def __init__(self):
        self.provider_order = [
            ("Gemini", analyze_with_gemini),
            ("OpenAI", analyze_with_openai),
            ("Claude", analyze_with_anthropic),
        ]

    def analyze_image(self, image_input):
        image = normalize_image(image_input)

        errors = []

        for provider_name, provider_function in self.provider_order:

            try:
                result = provider_function(image)

                result["ai_provider"] = provider_name

                # Keep uncertainty visible to the user.
                result["warnings"] = list(
                    result.get("warnings", [])
                )

                result["warnings"].append(
                    f"Analysis generated by {provider_name}. "
                    "Verify product identity and measurements."
                )

                return normalize_result(result)

            except Exception as error:
                message = str(error).strip()

                # Avoid displaying arbitrarily long provider errors.
                if len(message) > 350:
                    message = message[:350] + "..."

                errors.append(
                    f"{provider_name}: {message}"
                )

        raise RuntimeError(
            "All configured AI providers failed.\n\n"
            + "\n".join(errors)
        )