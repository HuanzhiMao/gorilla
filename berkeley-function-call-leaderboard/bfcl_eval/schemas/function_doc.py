"""Tool definitions as the model sees them.

BFCL's parameter schema is a JSON-Schema *dialect*, not JSON Schema: the top-level
type is spelled ``"dict"`` rather than ``"object"``, and the corpus uses BFCL type
names (``float``, ``any``, ``tuple``, ``ArrayList``, ``Array``) plus two keys that
are not JSON Schema at all (``optional``, ``additionalProperties``).

That is why ``ParameterSchema`` parses rather than validates, and why its ``extras``
bucket is mandatory: a corpus-wide survey found 13 distinct schema keys, and the
long tail (``format``, ``maximum``, ``minItems``, ``maxItems``) has single-digit
occurrence counts that would be lost by a stricter model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator

from bfcl_eval.schemas.serde import PARAMETER_DIALECT_KEYS, dump_extras, split_known


class _Unset:
    """Sentinel distinguishing "key absent" from "key present with value null"."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = _Unset()


@dataclass(frozen=True, slots=True)
class ParameterSchema:
    """One node of a BFCL parameter schema tree.

    Frozen: ``_func_doc_language_specific_pre_processing`` currently mutates schema
    nodes in place, and the docs it mutates come from a shared per-class file. The
    moment that loader is memoised, in-place mutation becomes cross-entry
    corruption. Making the node immutable turns that transform into a pure one and
    the bug unrepresentable.
    """

    type: str
    description: str | None = None
    # Sub-schemas by property name.
    #
    # Values are normally ``ParameterSchema``, but 771 nodes in the corpus -- all
    # inside ``response`` schemas -- use a bare prose string instead of a schema
    # object (e.g. ``{"contact": "Dict[str, Any]: The created contact object."}``).
    # Those pass through verbatim rather than being coerced or dropped.
    properties: dict[str, "ParameterSchema | Any"] | None = None
    # Element schema for array types. Normally a ``ParameterSchema``; two nodes in
    # ``memory_kv.json`` use a *list* of schemas to express a tuple type, which is
    # preserved as-is.
    items: "ParameterSchema | Any | None" = None
    required: tuple[str, ...] | None = None
    enum: tuple[Any, ...] | None = None
    default: Any = UNSET
    extras: dict[str, Any] = field(default_factory=dict, repr=False)
    # The key order this node had on disk, so ``to_dict`` can reproduce it.
    #
    # Ordering is normally invisible -- dict equality ignores it. It matters here
    # because the JavaScript language hint embeds ``json.dumps(properties)`` directly
    # into a tool description that the model reads, so a reordered key changes the
    # prompt. Empty for schemas built in code, which then get the canonical order.
    wire_key_order: tuple[str, ...] = field(default=(), repr=False, compare=False)

    _WIRE_KEYS = frozenset(
        {"type", "description", "properties", "items", "required", "enum", "default"}
    )

    @staticmethod
    def _parse_node(value: Any) -> Any:
        """Parse a nested schema, passing non-object values through untouched."""
        return ParameterSchema.from_dict(value) if isinstance(value, dict) else value

    @staticmethod
    def _dump_node(value: Any) -> Any:
        return value.to_dict() if isinstance(value, ParameterSchema) else value

    @classmethod
    def from_dict(cls, raw: dict) -> "ParameterSchema":
        known, annotations, extras = split_known(
            raw, cls._WIRE_KEYS, silent=PARAMETER_DIALECT_KEYS
        )
        properties = known.get("properties")
        required = known.get("required")
        enum = known.get("enum")
        return cls(
            type=known["type"],
            description=known.get("description"),
            properties=(
                {name: cls._parse_node(sub) for name, sub in properties.items()}
                if isinstance(properties, dict)
                else properties
            ),
            items=cls._parse_node(known["items"]) if "items" in known else None,
            required=tuple(required) if required is not None else None,
            enum=tuple(enum) if enum is not None else None,
            default=known.get("default", UNSET),
            # Parameter schemas have no `_`-prefixed keys today; if one appears it
            # belongs with the other unmodeled keys rather than in its own bucket.
            extras=dump_extras({}, annotations, extras),
            wire_key_order=tuple(raw),
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {"type": self.type}
        if self.description is not None:
            out["description"] = self.description
        if self.properties is not None:
            out["properties"] = (
                {name: self._dump_node(sub) for name, sub in self.properties.items()}
                if isinstance(self.properties, dict)
                else self.properties
            )
        if self.items is not None:
            out["items"] = self._dump_node(self.items)
        if self.required is not None:
            out["required"] = list(self.required)
        if self.enum is not None:
            out["enum"] = list(self.enum)
        if self.default is not UNSET:
            out["default"] = self.default
        dump_extras(out, self.extras)
        return self._in_wire_order(out)

    def _in_wire_order(self, out: dict) -> dict:
        """Reorder ``out`` to match the key order this node had on disk."""
        if not self.wire_key_order:
            return out
        ordered = {key: out[key] for key in self.wire_key_order if key in out}
        ordered.update({key: value for key, value in out.items() if key not in ordered})
        return ordered

    def walk(self) -> Iterator["ParameterSchema"]:
        """Pre-order traversal of this node and every nested ``ParameterSchema``.

        Non-schema property values and list-valued ``items`` are skipped.
        """
        yield self
        properties = self.properties if isinstance(self.properties, dict) else {}
        for sub in properties.values():
            if isinstance(sub, ParameterSchema):
                yield from sub.walk()
        if isinstance(self.items, ParameterSchema):
            yield from self.items.walk()


@dataclass(frozen=True, slots=True)
class FunctionDoc:
    """A single tool definition.

    Four wire keys, not three: ``response`` appears on 940 of the 951 entries in
    ``data/multi_turn_func_doc/`` and is folded into ``description`` (then deleted)
    for some provider styles. A model that knows only ``{name, description,
    parameters}`` drops it silently.
    """

    name: str
    description: str
    parameters: ParameterSchema
    response: ParameterSchema | None = None
    extras: dict[str, Any] = field(default_factory=dict, repr=False)

    _WIRE_KEYS = frozenset({"name", "description", "parameters", "response"})

    @property
    def properties(self) -> dict[str, ParameterSchema]:
        return self.parameters.properties or {}

    @property
    def required(self) -> tuple[str, ...]:
        return self.parameters.required or ()

    def param(self, name: str) -> ParameterSchema | None:
        return self.properties.get(name)

    @classmethod
    def from_dict(cls, raw: dict) -> "FunctionDoc":
        known, annotations, extras = split_known(raw, cls._WIRE_KEYS)
        response = known.get("response")
        return cls(
            name=known["name"],
            description=known.get("description", ""),
            parameters=ParameterSchema.from_dict(known["parameters"]),
            response=ParameterSchema.from_dict(response) if isinstance(response, dict) else None,
            extras=dump_extras({}, annotations, extras),
        )

    def to_dict(self) -> dict:
        out: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters.to_dict(),
        }
        if self.response is not None:
            out["response"] = self.response.to_dict()
        return dump_extras(out, self.extras)
