
"""
VisionWrap AI Product Recognition
Uses CLIP zero-shot image recognition.

Preserves the existing interface:
    Recognizer(names)
    recognizer.rank(image_rgb, top_k=3)

No training or ArUco markers are required for AI recognition.
"""

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

MODEL_NAME = "openai/clip-vit-base-patch32"

TEMPLATES = [
    "a photo of a {}",
    "a close-up photo of a {} on a table",
    "a product photo of a {}",
]


try:
    AVAILABLE = True
except Exception:
    AVAILABLE = False


class Recognizer:

    def __init__(self, names):
        self.names = list(names)

        if not self.names:
            raise ValueError(
                "No product names were provided for recognition."
            )

        self.device = (
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.processor = CLIPProcessor.from_pretrained(
            MODEL_NAME
        )

        self.model = CLIPModel.from_pretrained(
            MODEL_NAME
        ).to(self.device).eval()

        self.text_emb = self._encode_text()

    def _encode_text(self):
        embeddings = []

        with torch.no_grad():

            for name in self.names:

                prompts = [
                    template.format(name.lower())
                    for template in TEMPLATES
                ]

                inputs = self.processor(
                    text=prompts,
                    return_tensors="pt",
                    padding=True
                )

                inputs = {
                    key: value.to(self.device)
                    for key, value in inputs.items()
                }

                # Explicitly obtain the text feature tensor.
                features = self.model.get_text_features(
                    **inputs
                )

                # Handle Transformers versions that return
                # a model output object instead of a tensor.
                if hasattr(features, "text_embeds"):
                    features = features.text_embeds
                elif not isinstance(features, torch.Tensor):
                    raise TypeError(
                        "Unable to extract text features from CLIP."
                    )

                features = features / features.norm(
                    dim=-1,
                    keepdim=True
                ).clamp(min=1e-12)

                # Combine the three text descriptions.
                features = features.mean(dim=0)

                features = features / features.norm().clamp(
                    min=1e-12
                )

                embeddings.append(features)

        return torch.stack(embeddings)

    def rank(self, image_rgb, top_k=3):
        """
        Args:
            image_rgb: Image represented as an RGB NumPy array.
            top_k: Number of product suggestions.

        Returns:
            List of (product_name, score) tuples,
            ordered from highest score to lowest.
        """

        if image_rgb is None:
            raise ValueError("No image was provided.")

        pil_image = Image.fromarray(
            np.asarray(image_rgb, dtype=np.uint8)
        ).convert("RGB")

        inputs = self.processor(
            images=pil_image,
            return_tensors="pt"
        )

        inputs = {
            key: value.to(self.device)
            for key, value in inputs.items()
        }

        with torch.no_grad():

            # Explicitly obtain image feature embeddings.
            image_features = self.model.get_image_features(
                **inputs
            )

            # Support Transformers versions that return
            # a model output object instead of a tensor.
            if hasattr(image_features, "image_embeds"):
                image_features = image_features.image_embeds
            elif not isinstance(image_features, torch.Tensor):
                raise TypeError(
                    "Unable to extract image features from CLIP."
                )

            image_features = image_features / image_features.norm(
                dim=-1,
                keepdim=True
            ).clamp(min=1e-12)

            # Compare the image with the product descriptions.
            logits = 100.0 * (
                image_features @ self.text_emb.T
            )

            scores = torch.softmax(
                logits,
                dim=-1
            )[0].cpu().numpy()

        count = min(max(1, int(top_k)), len(self.names))

        order = np.argsort(-scores)[:count]

        return [
            (self.names[index], float(scores[index]))
            for index in order
        ]
