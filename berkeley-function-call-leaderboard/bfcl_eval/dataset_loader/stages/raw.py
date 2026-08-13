"""Stages that run before parsing, on raw JSON objects.

These change an entry's *identity* -- its id, or its very shape -- so they have to run
before the entry is turned into a typed object.

``assign_ids`` runs first and is the **only** place an entry id is composed. Everything
downstream treats ids as opaque: stages copy them, and the category an entry belongs to
travels as :data:`~bfcl_eval.schemas.entries.CATEGORY_STAMP` rather than being spelled
into the id for a later stage to decode.
"""

from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path

from bfcl_eval.constants.category_mapping import MEMORY_SCENARIO_NAME
from bfcl_eval.constants.eval_config import IMAGE_PATH, MEMORY_PREREQ_CONVERSATION_PATH
from bfcl_eval.dataset_loader.jsonl import read_entries
from bfcl_eval.dataset_loader.pipeline import LoadContext
from bfcl_eval.schemas.category import TestCategory
from bfcl_eval.schemas.entries import CATEGORY_STAMP

# Image-variant filename suffixes for the vision web-search perturbations, keyed by
# base category name.
#
# These keys used to be spelled ``"vision_bw"``, ``"vision_crop_169"``, ... while the
# lookup key is the *base category name*, so the lookup never matched and all eight
# variants silently scored the unperturbed image. ``vision_web_search_base`` is absent
# on purpose: it is the unperturbed variant.
VISION_SUFFIX_MAP = {
    "vision_web_search_crop_169": "_169",
    "vision_web_search_crop_43": "_43",
    "vision_web_search_resize_169": "_resize_169",
    "vision_web_search_resize_43": "_resize_43",
    "vision_web_search_bw": "_bw",
    "vision_web_search_edge": "_edge",
    "vision_web_search_rg": "_rg",
}


def compose_id(raw_id: str, category: TestCategory) -> str:
    """Compose an entry's final id: ``memory_prereq_0-customer-0`` ->
    ``text:memory_kv_prereq_0-customer-0``.

    Two things happen at once, and both are rewrites of the *leading* segment:

    * **Modality.** The same questions ship as text and as speech, and are scored
      separately, so a bare id names a question rather than a test case.
    * **Category.** Several categories share one source file -- six read
      ``memory.json``, eight read ``vision_web_search_base.json``, two read
      ``web_search.json`` -- so on-disk ids name the file, not the category reading it.

    Anchored at the front, unlike the ``str.replace`` calls this consolidates: those
    rewrite whichever occurrence of the stem they find first, so an id containing it
    twice would be corrupted silently. Here a stem that is not a prefix raises.
    """
    stem = category.spec.dataset_file_name().removesuffix(".json")
    remainder = raw_id[len(stem):] if raw_id.startswith(stem) else ""
    if not remainder.startswith("_"):
        raise ValueError(
            f"entry id {raw_id!r} does not start with {stem + '_'!r}, the stem of the "
            f"file {category.value} reads, so its index cannot be identified"
        )
    return f"{category.value}{remainder}"


def assign_ids(entries: list[dict], ctx: LoadContext) -> list[dict]:
    """Give every entry the id it will keep."""
    for entry in entries:
        entry["id"] = compose_id(entry["id"], ctx.category)
    return entries


def memory_prereq_link(entries: list[dict], ctx: LoadContext) -> list[dict]:
    """Expand a memory category into its questions plus their prerequisites.

    Each memory question is answered from memory that a *prerequisite* conversation
    has to write first, so this pulls in those conversations, points the questions at
    them via ``depends_on``, and pins both to the backend the category names.

    The nested shape below (one pass per scenario, each pass re-appending everything
    the previous pass produced) mirrors the original implementation exactly, including
    the fact that prerequisite entries from earlier scenarios are carried forward.

    The questions arrive with ids already assigned. The prerequisites do not -- they are
    read from a second file here, after ``assign_ids`` has run -- so this is the one
    other caller of :func:`compose_id`. They are stamped with the derived
    ``*_prereq`` category, which is how a single load yields two correctly-labelled
    kinds of entry without anyone parsing an id to tell them apart.
    """
    backend_class = f"MemoryAPI_{ctx.category.memory_backend}"
    prereq_category = ctx.category.prereq_variant

    for scenario in MEMORY_SCENARIO_NAME:
        prereq_entries = read_entries(
            MEMORY_PREREQ_CONVERSATION_PATH / f"memory_{scenario}.json"
        )
        expanded: list[dict] = []
        prereq_ids: list[str] = []

        for entry in prereq_entries:
            # Qualified against the *parent* category: these entries live in the
            # `memory_kv` id namespace and carry their own `_prereq` segment already.
            entry["id"] = compose_id(entry["id"], ctx.category)
            entry[CATEGORY_STAMP] = prereq_category
            entry["depends_on"] = deepcopy(prereq_ids)
            entry["involved_classes"] = [backend_class]
            prereq_ids.append(entry["id"])
            if ctx.include_prereq:
                expanded.append(entry)

        for entry in entries:
            if entry.get("scenario") == scenario:
                entry["depends_on"] = deepcopy(prereq_ids)
                entry["involved_classes"] = [backend_class]
            expanded.append(entry)

        entries = expanded

    return entries


def _image_path(image_file_name: str, suffix: str) -> Path:
    """Where a variant's image lives. ``suffix`` is empty for the unperturbed variant."""
    if not suffix:
        return IMAGE_PATH / image_file_name
    return IMAGE_PATH / image_file_name.replace(".jpeg", f"{suffix}.jpeg")


def _require_all_images(entries: list[dict], suffix: str, category) -> None:
    """Fail the whole category if any of its images is missing.

    A per-entry fallback to the unperturbed image would be worse than failing: the
    category would still report a score, but some of its entries would silently not be
    testing the perturbation the category exists to measure. Better to refuse to load
    and say exactly which files are needed.

    Checked up front rather than lazily so one run names every missing file, instead of
    dying on whichever entry happens to come first.
    """
    missing = sorted(
        {
            _image_path(entry["image_file_name"], suffix).name
            for entry in entries
            if not _image_path(entry["image_file_name"], suffix).exists()
        }
    )
    if not missing:
        return

    shown = ", ".join(missing[:10]) + (f", ... (+{len(missing) - 10} more)" if len(missing) > 10 else "")
    raise FileNotFoundError(
        f"Cannot load {category.value}: {len(missing)} of its {len(entries)} images are "
        f"missing from {IMAGE_PATH} -- {shown}. Every image needs its "
        f"{suffix.lstrip('_')!r} variant for this category to measure that perturbation; "
        f"generate them or drop the category."
    )


def vision_attach_image(entries: list[dict], ctx: LoadContext) -> list[dict]:
    """Rebuild each vision entry around the image its question refers to.

    The on-disk entry names an image file; the model needs the bytes. Everything else
    about the entry is discarded, which is why this runs before parsing -- the id
    included, so it is carried across verbatim rather than rebuilt.
    """
    suffix = VISION_SUFFIX_MAP.get(ctx.category.base_name, "")
    _require_all_images(entries, suffix, ctx.category)

    rebuilt = []
    for entry in entries:
        image_path = _image_path(entry["image_file_name"], suffix)
        with open(image_path, "rb") as image_file:
            image_bytes = image_file.read()

        rebuilt.append(
            {
                "involved_classes": ["VisionSearchAPI"],
                "id": entry["id"],
                "question": [
                    [
                        {
                            "role": "user",
                            "content": entry["question"][0][0]["content"],
                            "image_content": [
                                {
                                    "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
                                    "image_bytes": image_bytes,
                                    "image_path": str(image_path),
                                    "type": "image/jpeg",
                                }
                            ],
                        }
                    ]
                ],
            }
        )
    return rebuilt


def audio_materialize(entries: list[dict], ctx: LoadContext) -> list[dict]:
    """Replace each user message's text with its spoken form.

    Delegates to the original implementation rather than reimplementing it, because
    this stage is currently **unreachable** and so an untested reimplementation of
    ~60 lines would be a liability rather than an improvement. Two defects make it
    unreachable:

    * ``MODALITY_DATASET_PATH`` maps both audio modalities to ``data/audio/``, but that
      directory contains only sub-directories (``text_audio/``, ``audio_recording_clean/``,
      ...) -- there is no ``data/audio/<category>.json`` to read, so the load fails
      before any stage runs.
    * Even given the files, the delegate deletes ``asr_output_openai`` /
      ``asr_output_elevenlabs`` / ``asr_output_deepgram``, while the audio corpus spells
      those ``asr_{engine}_audio_{clean,noisy}`` -- so it would raise ``KeyError``.

    Once the dataset side is fixed, this is the place to write a typed implementation.
    """
    from bfcl_eval.utils import process_audio_test_case

    return process_audio_test_case(entries, modality=ctx.category.modality)
