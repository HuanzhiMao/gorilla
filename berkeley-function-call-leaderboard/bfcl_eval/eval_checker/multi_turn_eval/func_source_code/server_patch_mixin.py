"""
Runtime patches for API methods.

All API classes in func_source_code inherit from PatchableMixin, which provides:
  - A per-class patch registry  (cls._PATCHES)
  - cls._register_patch(method_name, patch_name)  — decorator to register a patch
  - instance._apply_patch(method_name, patch_name) — apply a registered patch

Usage:
    from posting_api import TwitterAPI

    @TwitterAPI._register_patch("search_tweets", "scenario_1")
    def search_tweets_scenario_1(self, keyword):
        ...

    api = TwitterAPI()
    api._apply_patch("search_tweets", "scenario_1")

    # Check per-method call counts via api._patch_call_count_mapping
    # e.g. api._patch_call_count_mapping["search_tweets"]
"""

import types


class PatchableMixin:
    """Mixin that gives any API class a per-class patch registry."""

    @classmethod
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Each subclass gets its own registry so patches don't leak between classes.
        cls._PATCHES = {}

    @classmethod
    def _register_patch(cls, method_name, patch_name):
        """Decorator to register a patch on this class."""
        if not hasattr(cls, "_PATCHES") or "_PATCHES" not in cls.__dict__:
            cls._PATCHES = {}

        def decorator(fn):
            cls._PATCHES.setdefault(method_name, {})[patch_name] = fn
            return fn
        return decorator

    def _apply_patch(self, method_name: str, patch_name: str):
        """Apply a named patch to a method on this instance."""
        class_patches = self.__class__.__dict__.get("_PATCHES", {})
        if method_name not in class_patches or patch_name not in class_patches[method_name]:
            available = sorted(class_patches.get(method_name, {}).keys())
            raise ValueError(
                f"Unknown patch '{patch_name}' for '{method_name}'. Available: {available}"
            )

        if not hasattr(self, "_patch_call_count_mapping"):
            self._patch_call_count_mapping = {}
        self._patch_call_count_mapping[method_name] = 0

        original = getattr(self, method_name)
        patch_fn = class_patches[method_name][patch_name]

        def wrapper(self, *args, **kwargs):
            self._patch_call_count_mapping[method_name] += 1
            self._patch_call_count = self._patch_call_count_mapping[method_name]
            self._original_function = original
            return patch_fn(self, *args, **kwargs)

        setattr(self, method_name, types.MethodType(wrapper, self))
