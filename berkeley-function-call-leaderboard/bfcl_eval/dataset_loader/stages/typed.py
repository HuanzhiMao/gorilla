"""Stages that run after parsing, on typed ``TestEntry`` objects.

These are the universal tail of every category's pipeline. Each one no-ops for the
categories it does not apply to, which is why they are shared rather than declared
per row.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace

from bfcl_eval.constants.default_prompts import (
    ADDITIONAL_SYSTEM_PROMPT_FOR_AGENTIC_RESPONSE_FORMAT,
)
from bfcl_eval.constants.enums import Language
from bfcl_eval.constants.eval_config import (
    MULTI_TURN_FUNC_DOC_PATH,
    SERVER_INITIAL_CONFIG_VARIANT_PATH,
)
from bfcl_eval.constants.executable_backend_config import (
    LONG_CONTEXT_CONFIG_KEY,
    MULTI_TURN_FUNC_DOC_FILE_MAPPING,
)
from bfcl_eval.dataset_loader.jsonl import read_entries
from bfcl_eval.dataset_loader.pipeline import LoadContext
from bfcl_eval.schemas.entries import TestEntry
from bfcl_eval.schemas.function_doc import FunctionDoc, ParameterSchema


def resolve_initial_config(entries: list[TestEntry], ctx: LoadContext) -> list[TestEntry]:
    """Replace ``initial_config`` path strings with the JSON they point at.

    A backend's starting state is usually written inline, but the failing-tools
    category factors its variants out into ``server_initial_config_variant/`` and
    refers to them by path.

    An entry whose config file cannot be read is a hard error. It used to be dropped
    with a warning, which shortened the prompt list while leaving the ground-truth file
    intact -- a dataset typo would quietly reduce the number of scored entries rather
    than failing the run.
    """
    for entry in entries:
        config = entry.environment.initial_config
        if not isinstance(config, dict):
            continue
        for class_name, value in config.items():
            if not isinstance(value, str):
                continue
            path = (SERVER_INITIAL_CONFIG_VARIANT_PATH / value).resolve()
            try:
                with open(path) as f:
                    config[class_name] = json.load(f)
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(
                    f"Entry '{entry.id}' (source: "
                    f"{entry.annotations.get('_source', 'N/A')}) names an initial_config "
                    f"for {class_name} that cannot be read: {path} ({exc})"
                ) from exc
    return entries


def mark_long_context(entries: list[TestEntry], ctx: LoadContext) -> list[TestEntry]:
    """Record long-context mode in each backend's ``initial_config`` blob.

    Long context is a property of the *starting state*: the backends splice bulk records
    from ``func_source_code/long_context.py`` into the state they build in
    ``_load_scenario``. Writing it into ``initial_config`` puts it where that state
    already lives, so it reaches the backends as data.

    That matters because two callers build those backends -- the handler during
    generation and the checker during scoring -- and both already thread
    ``initial_config`` through. Carrying the flag alongside it means they cannot
    disagree; the checker used to re-derive it by testing whether ``"long_context"``
    appeared in the category name.

    Written into each per-class blob rather than as one key beside them, because a blob
    is exactly what ``_load_scenario`` receives: nothing between here and the backend
    then has to know this flag exists. It also keeps ``initial_config`` a plain mapping
    of class name to config, which ``resolve_initial_config`` above and the executor
    both assume.

    Written only when true. An absent key is off, so every other category's
    ``initial_config`` is left byte-identical to what the dataset file holds.

    Read per entry rather than off ``ctx.category``, because a load can yield entries
    from more than one category: a memory load also emits its prerequisite entries,
    whose spec is its own. ``structured_answer_prompt`` splits on the same seam.
    """
    for entry in entries:
        if entry.category.long_context:
            for class_config in entry.environment.initial_config.values():
                class_config[LONG_CONTEXT_CONFIG_KEY] = True
    return entries


def structured_answer_prompt(entries: list[TestEntry], ctx: LoadContext) -> list[TestEntry]:
    """Ask agentic categories to end with a parseable final answer.

    The checker for these categories reads the model's last non-tool-call message, so
    the model has to be told what shape that message should take.

    Applies to web search, memory questions, geoguessr, and vision web search --
    ``requires_structured_answer`` on the category spec. Memory *prerequisite*
    conversations are excluded: they write to memory rather than answering anything.
    """
    for entry in entries:
        if entry.category.requires_structured_answer:
            entry.conversation.prepend_system_message(
                ADDITIONAL_SYSTEM_PROMPT_FOR_AGENTIC_RESPONSE_FORMAT
            )
    return entries


def _backend_func_docs(class_name: str) -> list[FunctionDoc]:
    raw = read_entries(MULTI_TURN_FUNC_DOC_PATH / MULTI_TURN_FUNC_DOC_FILE_MAPPING[class_name])
    return [FunctionDoc.from_dict(doc) for doc in raw]


def resolve_tools(entries: list[TestEntry], ctx: LoadContext) -> list[TestEntry]:
    """Materialize the tool list for entries that name backend classes.

    Multi-turn and agentic entries do not spell out their tools -- they name the API
    server classes they run against, and the tool docs come from those. Entries that
    ship an explicit ``function`` list are left alone.
    """
    for entry in entries:
        if "involved_classes" not in entry.present_keys:
            continue
        entry.functions = [
            doc
            for class_name in entry.environment.involved_classes
            for doc in _backend_func_docs(class_name)
        ]
    return entries


def resolve_holdout_docs(entries: list[TestEntry], ctx: LoadContext) -> list[TestEntry]:
    """Withhold the tools a holdout rule covers, keeping them on the rule.

    ``multi_turn_miss_func`` and ``failing_tools`` test whether a model copes when a
    tool it needs is missing and then appears. The docs are removed from the entry's
    live tool list here, and handed back by ``TestEntry.release_holdout`` when the
    rule fires mid-episode.
    """
    for entry in entries:
        if "missed_classes" not in entry.present_keys:
            continue
        for rule in entry.environment.holdout_rules:
            withheld: list[FunctionDoc] = []

            # Withhold whole backends.
            for class_name in rule.holdout_classes:
                class_docs = _backend_func_docs(class_name)
                withheld.extend(class_docs)
                withheld_names = {doc.name for doc in class_docs}
                entry.functions = [
                    doc for doc in entry.functions if doc.name not in withheld_names
                ]

            # Withhold individual tools.
            for func_name in rule.holdout_functions:
                for index, doc in enumerate(entry.functions):
                    if doc.name == func_name:
                        withheld.append(doc)
                        entry.functions.pop(index)
                        break

            rule.holdout_docs = withheld
    return entries


def _language_hint_sentence(category) -> str:
    """The one-sentence syntax note appended to every tool description."""
    from bfcl_eval.utils import _get_language_specific_hint

    return _get_language_specific_hint(category.language)


def _java_parameter_hint(schema: ParameterSchema) -> ParameterSchema:
    description = schema.description or ""
    if schema.type == "any":
        description += " This parameter can be of any type of Java object in string representation."
    else:
        description += f" This is Java {schema.type} type parameter in string representation."

    items = schema.items
    if schema.type in ("ArrayList", "Array"):
        description += (
            f" The list elements are of type {items.type}; "
            f"they are not in string representation."
        )
        items = None

    return replace(schema, description=description, items=items, type="string")


def _javascript_parameter_hint(schema: ParameterSchema) -> ParameterSchema:
    description = schema.description or ""
    if schema.type == "any":
        description += (
            " This parameter can be of any type of JavaScript object in string representation."
        )
    else:
        description += f" This is JavaScript {schema.type} type parameter in string representation."

    items, properties = schema.items, schema.properties
    if schema.type == "array":
        description += (
            f" The list elements are of type {items.type}; "
            f"they are not in string representation."
        )
        items = None
    if schema.type == "dict" and properties is not None:
        rendered = {name: sub.to_dict() for name, sub in properties.items()}
        description += (
            f" The dictionary entries have the following schema; they are not in "
            f"string representation. {json.dumps(rendered)}"
        )
        properties = None

    return replace(
        schema, description=description, items=items, properties=properties, type="string"
    )


def language_hint(entries: list[TestEntry], ctx: LoadContext) -> list[TestEntry]:
    """Tell the model how a non-Python language's types arrive.

    Java and JavaScript calls are evaluated as strings, so every parameter is declared
    as a string and its real type is described in prose instead. For Python this only
    appends the standard hint to each description.
    """
    if not ctx.include_language_specific_hint:
        return entries

    for entry in entries:
        if not entry.functions:
            continue
        language = entry.category.language
        hint = _language_hint_sentence(entry.category)

        rewritten = []
        for doc in entry.functions:
            parameters = doc.parameters
            if language is Language.JAVA:
                convert = _java_parameter_hint
            elif language is Language.JAVASCRIPT:
                convert = _javascript_parameter_hint
            else:
                convert = None

            if convert is not None and parameters.properties:
                parameters = replace(
                    parameters,
                    properties={
                        name: convert(sub) for name, sub in parameters.properties.items()
                    },
                )

            rewritten.append(
                replace(doc, description=doc.description + hint, parameters=parameters)
            )
        entry.functions = rewritten
    return entries
