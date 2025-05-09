from __future__ import annotations
"""
Tiny knowledge‑graph helper built on NetworkX
--------------------------------------------
Changes in this revision
  • **add_entity** and **add_relation** now expect a *single* parameter
    ``attrs`` that is **a JSON string** (or ``None``). The string is parsed
    with ``json.loads``; the resulting dictionary becomes the node/edge
    properties.

Summary of features
  • add_entity(id, attrs:str|None)
  • add_relation(source, target, rel_type, attrs:str|None)
  • get_entity(id)
  • get_relations(source, rel_type=None)
  • list_entities(), list_relations()
  • build_embeddings(attr="name") / search_similar()
  • save(path) / load(path)

Dependencies
  • networkx
  • sentence‑transformers (model: "all-MiniLM-L6-v2" on CPU)
  • numpy
"""
import json
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional

import networkx as nx
from networkx.readwrite import json_graph
import numpy as np
from sentence_transformers import SentenceTransformer

# -----------------------------------------------------------------------------
# Helper for parsing the attrs JSON string
# -----------------------------------------------------------------------------

def _parse_attrs(attrs: Optional[str]) -> Dict[str, Any]:
    """Safely parse *attrs* JSON string into a dict.

    Returns an empty dict if *attrs* is "". Raises ``ValueError`` if
    the string cannot be parsed or does not decode to a JSON *object*.
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
    """In‑memory knowledge graph with JSON‑string attributes and embedding search."""


    # --------------------------------------------------------------------- init
    def __init__(self) -> None:
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        self._embeddings: dict[str, np.ndarray] = {}
        self._encoder = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")


    def add_entity(self, eid: str, attrs: Optional[str] = "") -> None:
        """
        Insert a node to the graph with properties from JSON string.
        
        Args:
            eid (str): The entity ID, which must be unique.
            attrs (str): [Optional] JSON string representing the attributes of the entity. It must be json-loadable.
        
        Returns:
        
        """
        props = _parse_attrs(attrs)
        self._g.add_node(eid, **props)
        self._embeddings.pop(eid, None)  # reset cached embedding

    def add_relation(
        self,
        src: str,
        dst: str,
        rel_type: str,
        attrs: Optional[str] = None,
    ) -> None:
        """Insert a directed edge with properties from JSON string."""
        edge_props = _parse_attrs(attrs)
        # store the relation type explicitly as an edge property
        self._g.add_edge(src, dst, key=rel_type, type=rel_type, **edge_props)

    def update_entity(self, eid: str, attrs: Optional[str]) -> None:
        """Patch existing entity properties with *attrs* JSON string."""
        if eid not in self._g:
            raise KeyError(f"Entity {eid!r} not found")
        self._g.nodes[eid].update(_parse_attrs(attrs))
        self._embeddings.pop(eid, None)

    # removal helpers were requested conceptually but not implemented earlier
    def delete_entity(self, eid: str, cascade: bool = True) -> None:
        if eid not in self._g:
            return
        if cascade:
            self._g.remove_node(eid)
        else:
            if self._g.degree(eid) != 0:
                raise ValueError("Entity has relationships; use cascade=True")
            self._g.remove_node(eid)
        self._embeddings.pop(eid, None)

    def delete_relation(self, src: str, dst: str, rel_type: str) -> None:
        self._g.remove_edge(src, dst, key=rel_type)

    # ---------------------------------------------------------------- look‑ups
    def get_entity(self, eid: str) -> Dict[str, Any] | None:
        return self._g.nodes[eid] if eid in self._g else None

    def get_relations(
        self, src: str, rel_type: str | None = None
    ) -> List[Dict[str, Any]]:
        if src not in self._g:
            return []
        out: list[dict] = []
        for _, dst, key, attrs in self._g.out_edges(src, keys=True, data=True):
            if rel_type is None or key == rel_type:
                out.append({"source": src, "target": dst, **attrs})
        return out

    # ----------------------------------------------------------- discovery APIs
    def list_entities(self) -> List[str]:
        return list(self._g.nodes)

    def list_relations(
        self, rel_type: str | None = None
    ) -> List[Tuple[str, str, str, dict]]:
        rels: list[tuple[str, str, str, dict]] = []
        for src, dst, key, attrs in self._g.edges(keys=True, data=True):
            if rel_type is None or key == rel_type:
                rels.append((src, dst, key, attrs))
        return rels

    # ------------------------------------------------ embedding‑based similarity
    def build_embeddings(self, attr: str = "name") -> None:
        texts, nids = [], []
        for nid, data in self._g.nodes(data=True):
            texts.append(str(data.get(attr, nid)))
            nids.append(nid)
        if not texts:
            return
        vecs = self._encoder.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        self._embeddings = dict(zip(nids, vecs))

    def search_similar(
        self, query: str, top_k: int = 5, attr: str = "name"
    ) -> List[Tuple[str, float]]:
        if not self._embeddings:
            self.build_embeddings(attr)
        q_vec = self._encoder.encode(query, convert_to_numpy=True, show_progress_bar=False)
        q_norm = np.linalg.norm(q_vec)
        sims: list[Tuple[str, float]] = []
        for nid, vec in self._embeddings.items():
            score = float(vec.dot(q_vec) / (np.linalg.norm(vec) * q_norm + 1e-12))
            sims.append((nid, score))
        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[:top_k]

    # ---------------------------------------------------------- persistence IO
    def save(self, path: str | Path) -> None:
        data = json_graph.node_link_data(self._g)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
        kg = cls()
        kg._g = json_graph.node_link_graph(data, multigraph=True, directed=True)
        return kg

    # ------------------------------------------------------------- conveniences
    def __len__(self) -> int:
        return self._g.number_of_nodes()

    def __iter__(self):
        return iter(self._g.nodes)

    def __contains__(self, eid: str) -> bool:
        return eid in self._g

    def __str__(self) -> str:
        return f"<KnowledgeGraph | {len(self)} nodes, {self._g.number_of_edges()} edges>"
