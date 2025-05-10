from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import networkx as nx
from networkx.readwrite import json_graph
import numpy as np
from sentence_transformers import SentenceTransformer


def _parse_attrs(attrs: Optional[str]) -> Dict[str, Any]:
    """Safely parse *attrs* JSON string into a dict.

    Returns an empty dict if *attrs* is "". Raises ``ValueError`` if the
    string cannot be parsed or does not decode to a JSON *object*.
    """
    if not attrs:
        return {}
    try:
        obj = json.loads(attrs)
    except json.JSONDecodeError as e:
        raise ValueError(f"attrs is not valid JSON: {e.msg}") from None
    if not isinstance(obj, dict):
        raise ValueError("attrs JSON must decode to a dictionary object")
    return obj


class KnowledgeGraph:
    """In‑memory knowledge graph with JSON‑string attributes and embedding search.

    All public mutating and read‑only methods return a *dictionary* instead of
    ``None`` or bare values. This provides a consistent machine‑readable
    contract that can be safely serialized, logged or transmitted across
    process boundaries.

    Each returned mapping contains at minimum a ``status`` field describing the
    outcome of the operation. Additional keys may be added depending on the
    method (e.g. ``data``, ``entities``, ``relations``).
    """

    # --------------------------------------------------------------------- init
    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        self._embeddings: dict[str, np.ndarray] = {}
        # sentence‑transformers automatically handles caching; cpu is enough here
        self._encoder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

    # ---------------------------------------------------------------- entity APIs
    def add_entity(self, eid: str, attrs: Optional[str] = "") -> Dict[str, str]:
        """
        Insert a node to the graph with properties parsed from *attrs*.

        Args:
            eid (str): Unique identifier for the entity.
            attrs (str): [Optional] JSON string representing additional attributes, must be json-loadable.

        Returns:
            status (str): Status of the operation.
        """
        props = _parse_attrs(attrs)
        self._g.add_node(eid, **props)
        self._embeddings.pop(eid, None)  # reset cached embedding
        return {"status": "Entity added."}

    def update_entity(self, eid: str, attrs: Optional[str] = "") -> Dict[str, str]:
        """
        Patch properties of an existing entity.

        Args:
            eid (str): Entity identifier.
            attrs (str): JSON string with new attributes. If *attrs* is empty, the entity is not modified. If there are existing overlapping
                attributes, the new values will overwrite the old ones. If old values are not present in *attrs*, they will be kept.

        Returns:
            status (str): Status of the operation.
        """
        if eid not in self._g:
            return {"error": "Entity not found."}

        self._g.nodes[eid].update(_parse_attrs(attrs))
        self._embeddings.pop(eid, None)

        return {"status": "Entity updated."}

    def delete_entity(self, eid: str, cascade: Optional[bool] = True) -> Dict[str, Any]:
        """
        Remove an entity and, optionally, its relations.

        Args:
            eid (str): Entity identifier.
            cascade (bool): [Optional] If *True*, delete connected edges. If the node has relations and *cascade* is *False*, the operation will error.

        Returns:
            status (str): Status of the operation.
            cascade (bool): Whether the deletion was cascaded or not.
        """
        if eid not in self._g:
            return {"error": "Entity not found."}
        if cascade:
            self._g.remove_node(eid)
        else:
            if self._g.degree(eid) != 0:
                return {"error": "Entity has relations, cannot delete without cascade."}
            self._g.remove_node(eid)

        self._embeddings.pop(eid, None)

        return {"status": "Entity deleted.", "cascade": cascade}

    def get_entity(self, eid: str) -> Dict[str, str]:
        """
        Retrieve attributes of an entity.

        Args:
            eid (str): Entity identifier.

        Returns:
            status (str): Status of the operation.
            attributes (str): Entity attributes, formatted as a JSON string.
        """

        if eid not in self._g:
            return {"error": "Entity not found."}

        return {"status": "ok", "attributes": json.dumps(self._g.nodes[eid])}

    def add_relation(
        self,
        src: str,
        dst: str,
        rel_type: str,
        attrs: Optional[str] = "",
    ) -> Dict[str, str]:
        """
        Insert a directed edge (*src* → *dst*) with optional properties.

        Args:
            src (str): Source entity id.
            dst (str): Destination entity id.
            rel_type (str): Relation type, such as "friend", "colleague", etc.
            attrs (str): Optional JSON string with extra edge properties, must be json-loadable.

        Returns:
            status (str): Status of the operation.
        """
        edge_props = _parse_attrs(attrs)
        self._g.add_edge(src, dst, key=rel_type, type=rel_type, **edge_props)

        return {"status": "Relation added."}

    def delete_relation(self, src: str, dst: str, rel_type: str) -> Dict[str, str]:
        """
        Remove a relation by (*src*, *dst*, *rel_type*), case-sensitive.

        Args:
            src (str): Source entity id.
            dst (str): Destination entity id.
            rel_type (str): Relation type.

        Returns:
            status (str): Status of the operation.

        """
        try:
            self._g.remove_edge(src, dst, key=rel_type)
        except (KeyError, nx.NetworkXError):
            return {"error": "Relation not found."}

        return {"status": "Relation deleted."}

    def get_relations(self, src: str, rel_type: Optional[str] = None) -> Dict[str, Any]:
        """Return outgoing relations of *src* filtered by *rel_type*.

        Returns:
            dict: ``{"status": "ok", "relations": [ ... ]}`` or
            ``{"status": "not_found", "relations": []}``
        """
        if src not in self._g:
            return {"status": "not_found", "relations": []}
        out: list[dict] = []
        for _, dst, key, attrs in self._g.out_edges(src, keys=True, data=True):
            if rel_type is None or key == rel_type:
                out.append({"source": src, "target": dst, **attrs})
        return {"status": "ok", "relations": out}

    # ----------------------------------------------------------- discovery APIs
    def list_entities(self) -> Dict[str, Any]:
        """Return a list of all entity ids."""
        return {"status": "ok", "entities": list(self._g.nodes)}

    def list_relations(self, rel_type: Optional[str] = None) -> Dict[str, Any]:
        """List all relations, optionally filtered by type."""
        rels: list[tuple[str, str, str, dict]] = []
        for src, dst, key, attrs in self._g.edges(keys=True, data=True):
            if rel_type is None or key == rel_type:
                rels.append((src, dst, key, attrs))
        return {"status": "ok", "relations": rels}

    # ------------------------------------------------ embedding‑based similarity
    def build_embeddings(self, attr: str = "name") -> Dict[str, Any]:
        """Generate BERT‑style embeddings for all nodes.

        Args:
            attr: Node attribute to encode; defaults to ``"name"``.

        Returns:
            dict: ``{"status": "ok", "count": int}``
        """
        texts, nids = [], []
        for nid, data in self._g.nodes(data=True):
            texts.append(str(data.get(attr, nid)))
            nids.append(nid)
        if not texts:
            return {"status": "ok", "count": 0}
        vecs = self._encoder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        self._embeddings = dict(zip(nids, vecs))
        return {"status": "ok", "count": len(self._embeddings)}

    def search_similar(
        self, query: str, top_k: int = 5, attr: str = "name"
    ) -> Dict[str, Any]:
        """Return *top_k* most similar entities to *query* using cosine score."""
        if not self._embeddings:
            self.build_embeddings(attr)
        q_vec = self._encoder.encode(query, convert_to_numpy=True, show_progress_bar=False)
        q_norm = np.linalg.norm(q_vec)
        sims: list[Tuple[str, float]] = []
        for nid, vec in self._embeddings.items():
            score = float(vec.dot(q_vec) / (np.linalg.norm(vec) * q_norm + 1e-12))
            sims.append((nid, score))
        sims.sort(key=lambda x: x[1], reverse=True)
        return {"status": "ok", "results": sims[:top_k]}

    # ---------------------------------------------------------- persistence IO
    def save(self, path: str | Path) -> Dict[str, Any]:
        """Serialize the graph to *path* in node‑link JSON."""
        data = json_graph.node_link_data(self._g)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)
        return {"status": "saved", "path": str(path)}

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        """Load a graph from *path*. This still returns an instance, not a dict."""
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
        kg = cls()
        kg._g = json_graph.node_link_graph(data, multigraph=True, directed=True)
        return kg

    # ------------------------------------------------------------- conveniences
    def __len__(self) -> int:  # noqa: D401 – keep special method short
        return self._g.number_of_nodes()

    def __iter__(self):  # noqa: D401
        return iter(self._g.nodes)

    def __contains__(self, eid: str) -> bool:  # noqa: D401
        return eid in self._g

    def __str__(self) -> str:  # noqa: D401
        return f"<KnowledgeGraph | {len(self)} nodes, {self._g.number_of_edges()} edges>"
