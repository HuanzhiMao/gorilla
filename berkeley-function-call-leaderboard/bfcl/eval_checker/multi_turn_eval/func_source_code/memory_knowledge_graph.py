from __future__ import annotations
"""
Tiny knowledge‑graph helper built on NetworkX
--------------------------------------------
Features
  • add_entity(id, **attrs)
  • add_relation(source, target, rel_type, **attrs)
  • get_entity(id)
  • get_relations(source, rel_type=None)
  • list_entities()                       – enumerate node IDs
  • list_relations(rel_type=None)         – enumerate edges
  • build_embeddings(attr="name")          – pre‑compute text embeddings for a chosen attribute
  • search_similar(query, top_k=5)        – cosine‑similar nearest‑neighbour lookup over entity names
  • save(path) / load(path)               – JSON snapshot & restore

Dependencies
  • networkx
  • sentence‑transformers (we always use the model "all-MiniLM-L6-v2" on CPU)
  • numpy
"""
import json
from pathlib import Path
from typing import List, Tuple

import networkx as nx
from networkx.readwrite import json_graph
import numpy as np
from sentence_transformers import SentenceTransformer


class KnowledgeGraph:
    """A lightweight, in‑memory property graph with embedding‑based similarity search."""

    # persistent singleton ST model (CPU‑only, fixed model)
    _st_model = SentenceTransformer(
                "all-MiniLM-L6-v2", device="cpu"
            )

    # --------------------------------------------------------------------- init
    def __init__(self) -> None:
        # MultiDiGraph keeps multiple typed edges between the same pair
        self._g: nx.MultiDiGraph = nx.MultiDiGraph()
        # cache of text‑embeddings keyed by node id (filled lazily)
        self._embeddings: dict[str, np.ndarray] = {}

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _get_st_model() -> SentenceTransformer:
        """Return (and cache) a sentence‑transformer model on CPU."""
        if KnowledgeGraph._st_model is None:
            KnowledgeGraph._st_model = SentenceTransformer(
                "all-MiniLM-L6-v2", device="cpu"
            )
        return KnowledgeGraph._st_model

    # ------------------------------------------------------------- CRUD methods
    def add_entity(self, eid: str, **attrs) -> None:
        """Insert or update a node with optional attributes."""
        self._g.add_node(eid, **attrs)
        # clear embedding – will be recomputed lazily so cache stays consistent
        self._embeddings.pop(eid, None)

    def add_relation(self, src: str, dst: str, rel_type: str, **attrs) -> None:
        """Insert a directed edge (src‑[rel_type]->dst) with attributes."""
        self._g.add_edge(src, dst, key=rel_type, type=rel_type, **attrs)

    def get_entity(self, eid: str) -> dict | None:
        """Return the attribute dict for *eid* or ``None`` if missing."""
        return self._g.nodes[eid] if eid in self._g else None

    def get_relations(self, src: str, rel_type: str | None = None) -> List[dict]:
        """Return outgoing relations from *src* (optionally filtered by *rel_type*)."""
        if src not in self._g:
            return []
        results: list[dict] = []
        for _, dst, key, attrs in self._g.out_edges(src, keys=True, data=True):
            if rel_type is None or key == rel_type:
                results.append({"source": src, "target": dst, **attrs})
        return results
    
    def update_entity(self, eid: str, **attrs) -> None:
        if eid not in self._g:
            raise KeyError(f"{eid!r} not found")
        self._g.nodes[eid].update(attrs)
        self._embeddings.pop(eid, None)        # re‑compute on demand

    def delete_entity(self, eid: str, cascade: bool = True) -> None:
        if cascade:
            self._g.remove_node(eid)           # NetworkX drops incident edges
        else:
            if self._g.degree(eid) != 0:
                raise ValueError("Entity has relationships; use cascade=True")
            self._g.remove_node(eid)
        self._embeddings.pop(eid, None)

    def delete_relation(self, src: str, dst: str, rel_type: str) -> None:
        self._g.remove_edge(src, dst, key=rel_type)

        # ----------------------------------------------------------- discovery APIs
        def list_entities(self) -> List[str]:
            """Return all node IDs as a list (order is arbitrary)."""
            return list(self._g.nodes)

        def list_relations(
            self, rel_type: str | None = None
        ) -> List[Tuple[str, str, str, dict]]:
            """Return *all* relations.

            Each item is ``(source, target, rel_type, attrs)``.
            """
            rels: list[tuple[str, str, str, dict]] = []
            for src, dst, key, attrs in self._g.edges(keys=True, data=True):
                if rel_type is None or key == rel_type:
                    rels.append((src, dst, key, attrs))
            return rels

    # ------------------------------------------------ embedding‑based similarity
    def build_embeddings(self, attr: str = "name") -> None:
        """Compute or refresh text‑embeddings for all entities.

        *attr* – which node attribute to embed (falls back to node ID).
        """
        model = self._get_st_model()
        texts: list[str] = []
        nids: list[str] = []
        for nid, data in self._g.nodes(data=True):
            txt = str(data.get(attr, nid))
            texts.append(txt)
            nids.append(nid)
        if not texts:
            return
        vectors = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        self._embeddings = {nid: vec for nid, vec in zip(nids, vectors)}

    def search_similar(
        self,
        query: str,
        top_k: int = 5,
        attr: str = "name",
    ) -> List[Tuple[str, float]]:
        """Return *top_k* entity IDs most similar to *query*.

        Embeddings are built on demand the first time this method is called or
        when the cache is empty.
        """
        if not self._embeddings:
            self.build_embeddings(attr=attr)
        model = self._get_st_model()
        q_vec = model.encode(query, convert_to_numpy=True, show_progress_bar=False)
        q_norm = np.linalg.norm(q_vec)
        sims: list[Tuple[str, float]] = []
        for nid, vec in self._embeddings.items():
            score = float(vec.dot(q_vec) / (np.linalg.norm(vec) * q_norm + 1e-12))
            sims.append((nid, score))
        sims.sort(key=lambda x: x[1], reverse=True)
        return sims[: top_k]

    # ---------------------------------------------------------- persistence IO
    def save(self, path: str | Path) -> None:
        """Snapshot the graph to *path* (node‑link JSON). Embeddings are *not* stored."""
        data = json_graph.node_link_data(self._g)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(data, fp, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> "KnowledgeGraph":
        """Load a previously saved KnowledgeGraph."""
        with open(path, encoding="utf-8") as fp:
            data = json.load(fp)
        kg = cls()
        kg._g = json_graph.node_link_graph(data, multigraph=True, directed=True)
        return kg

    # ------------------------------------------------------------- conveniences
    def __len__(self) -> int:  # number of nodes
        return self._g.number_of_nodes()

    def __iter__(self):
        return iter(self._g.nodes)

    def __contains__(self, eid: str) -> bool:
        return eid in self._g

    def __str__(self) -> str:
        return (
            f"<KnowledgeGraph | {len(self)} nodes, "
            f"{self._g.number_of_edges()} edges>"
        )

    # raw underlying objects (escape hatch)
    def nodes(self):
        """Expose the raw NetworkX node view."""
        return self._g.nodes
