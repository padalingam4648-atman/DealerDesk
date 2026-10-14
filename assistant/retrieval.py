import math
import re
import threading
from collections import Counter, defaultdict
from django.db.models import Prefetch

from catalog.models import Product, Inventory
from common.money import format_money
from assistant.safety import sanitize_description

# Synonym mapping to bridge natural dealer queries with catalogue names
SYNONYM_MAP = {
    "pad": ["pad", "pads", "brake", "shoe"],
    "pads": ["pad", "pads", "brake", "shoe"],
    "brakepad": ["brake", "pad", "pads"],
    "brakepads": ["brake", "pad", "pads"],
    "shoe": ["shoe", "shoes", "brake"],
    "shoes": ["shoe", "shoes", "brake"],
    "filter": ["filter"],
    "filters": ["filter"],
    "oilfilter": ["oil", "filter"],
    "airfilter": ["air", "filter"],
    "chain": ["chain", "sprocket", "drive"],
    "chains": ["chain", "sprocket", "drive"],
    "sprocket": ["sprocket", "chain"],
    "sprockets": ["sprocket", "chain"],
    "rotor": ["disc", "rotor", "brake"],
    "rotors": ["disc", "rotor", "brake"],
    "disc": ["disc", "rotor", "brake"],
    "discs": ["disc", "rotor", "brake"],
    "lever": ["lever", "clutch", "brake"],
    "levers": ["lever", "clutch", "brake"],
    "plug": ["spark", "plug"],
    "plugs": ["spark", "plug"],
    "sparkplug": ["spark", "plug"],
    "grip": ["grip", "handle"],
    "grips": ["grip", "handle"],
    "cover": ["cover", "body"],
    "mirror": ["mirror", "side"],
    "mirrors": ["mirror", "side"],
}


def normalize_tokens(text: str) -> list[str]:
    """
    Tokenize and normalize text:
    - Lowercase and remove special characters
    - Split fused model codes (e.g. 'Duke390' -> 'duke', '390', 'FZ-S' -> 'fz', 's')
    - Expand common automotive synonyms
    """
    if not text:
        return []

    # Replace hyphens and slashes with spaces, but preserve alphanumerics
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    
    # Also separate letters and digits if fused (e.g. 'duke390' -> 'duke 390', 'mt15' -> 'mt 15')
    fused_split = re.sub(r"([a-z]+)(\d+)", r"\1 \2", cleaned)
    fused_split = re.sub(r"(\d+)([a-z]+)", r"\1 \2", fused_split)

    raw_tokens = fused_split.split()
    expanded_tokens = []

    for token in raw_tokens:
        expanded_tokens.append(token)
        if token in SYNONYM_MAP:
            expanded_tokens.extend(SYNONYM_MAP[token])

    return expanded_tokens


class ProductSearchIndex:
    """
    High-performance in-memory BM25 + Fitment retrieval engine for the catalogue.
    Built lazily on first access and cached in memory.
    """
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.doc_count = 0
        self.avg_doc_len = 0.0
        self.doc_lens = {}
        self.inverted_index = defaultdict(list)  # token -> list of (doc_id, tf)
        self.doc_sku_map = {}  # doc_id -> sku
        self.sku_doc_map = {}  # sku -> doc_id
        self.doc_fitment_map = {}  # doc_id -> vehicle_fitment normalized tokens
        self.doc_raw_fitment = {}  # doc_id -> raw vehicle fitment string
        self.idf = {}
        self.is_indexed = False

    @classmethod
    def get_instance(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def build_index(self):
        """
        Builds the BM25 index over all catalogue products.
        Runs in ~2-5ms for 600 products with zero external API dependencies.
        """
        with self._lock:
            products = list(Product.objects.all().only(
                "sku", "name", "category", "brand", "vehicle_fitment", "description"
            ))
            if not products:
                return

            self.doc_count = len(products)
            self.inverted_index.clear()
            self.doc_lens.clear()
            self.doc_sku_map.clear()
            self.sku_doc_map.clear()
            self.doc_fitment_map.clear()
            self.doc_raw_fitment.clear()

            total_tokens = 0
            df = defaultdict(int)

            for idx, p in enumerate(products):
                self.doc_sku_map[idx] = p.sku
                self.sku_doc_map[p.sku] = idx
                self.doc_raw_fitment[idx] = p.vehicle_fitment or ""
                self.doc_fitment_map[idx] = set(normalize_tokens(p.vehicle_fitment or ""))

                # Index document tokens
                text = f"{p.sku} {p.name} {p.category} {p.brand} {p.vehicle_fitment} {p.description or ''}"
                tokens = normalize_tokens(text)
                self.doc_lens[idx] = len(tokens)
                total_tokens += len(tokens)

                term_counts = Counter(tokens)
                for term, tf in term_counts.items():
                    self.inverted_index[term].append((idx, tf))
                    df[term] += 1

            self.avg_doc_len = total_tokens / max(1, self.doc_count)

            # Compute BM25 IDF
            self.idf = {}
            for term, count in df.items():
                self.idf[term] = math.log(1.0 + (self.doc_count - count + 0.5) / (count + 0.5))

            self.is_indexed = True

    def search(self, query: str, vehicle: str | None = None, limit: int = 5) -> list[str]:
        """
        Score products using BM25 and vehicle fitment matching.
        Returns list of SKUs ordered by relevance.
        """
        if not self.is_indexed or self.doc_count != Product.objects.count():
            self.build_index()

        if self.doc_count == 0:
            return []

        query_tokens = normalize_tokens(query)
        vehicle_tokens = set(normalize_tokens(vehicle)) if vehicle else set()

        scores = defaultdict(float)
        k1 = 1.5
        b = 0.75

        # 1. BM25 text relevance
        for term in set(query_tokens):
            if term not in self.inverted_index:
                continue
            idf_score = self.idf.get(term, 0.0)
            for doc_id, tf in self.inverted_index[term]:
                doc_len = self.doc_lens[doc_id]
                numerator = tf * (k1 + 1.0)
                denominator = tf + k1 * (1.0 - b + b * (doc_len / self.avg_doc_len))
                scores[doc_id] += idf_score * (numerator / denominator)

        # 2. Vehicle fitment matching and filtering
        scored_candidates = []
        for doc_id in range(self.doc_count):
            base_score = scores.get(doc_id, 0.0)
            sku = self.doc_sku_map[doc_id]

            # If user explicitly searched for an exact SKU
            if sku.lower() in [t.lower() for t in query.split()]:
                base_score += 50.0

            fitment_tokens = self.doc_fitment_map[doc_id]
            raw_fitment = self.doc_raw_fitment[doc_id]

            if vehicle_tokens:
                is_universal = "universal" in fitment_tokens or raw_fitment.lower() == "universal"
                # Check how well requested vehicle matches the product's fitment
                intersection = vehicle_tokens.intersection(fitment_tokens)

                if is_universal:
                    # Universal parts fit, but given a moderate score boost
                    vehicle_score = 4.0
                elif len(intersection) >= min(2, len(vehicle_tokens)):
                    # Strong direct model match (e.g. 'pulsar' + '150' matches 'Bajaj Pulsar 150')
                    vehicle_score = 15.0 + (len(intersection) * 2.0)
                elif len(intersection) > 0 and len(vehicle_tokens) == 1:
                    vehicle_score = 8.0
                else:
                    # Vehicle specified but product is specifically meant for another bike!
                    # Penalize severely to prevent recommending parts for the wrong vehicle
                    vehicle_score = -50.0
            else:
                vehicle_score = 0.0

            final_score = base_score + vehicle_score
            if final_score > 0:
                scored_candidates.append((doc_id, final_score))

        # Sort descending by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        top_skus = [self.doc_sku_map[doc_id] for doc_id, _ in scored_candidates[:limit]]
        return top_skus


def search_parts(query: str, vehicle: str | None = None, limit: int = 5) -> list[dict]:
    """
    Search catalogue products by query and optional vehicle fitment.
    Returns structured results populated with live price and stock from the database.
    """
    limit = max(1, min(10, int(limit) if limit else 5))
    index = ProductSearchIndex.get_instance()
    matching_skus = index.search(query=query, vehicle=vehicle, limit=limit)

    if not matching_skus:
        return []

    # Fetch live records and inventory from database
    products = {
        p.sku: p
        for p in Product.objects.filter(sku__in=matching_skus).select_related("inventory")
    }

    results = []
    for sku in matching_skus:
        if sku not in products:
            continue
        p = products[sku]
        stock_qty = p.inventory.quantity if hasattr(p, "inventory") and p.inventory else 0

        snippet = sanitize_description(p.description, max_chars=100)

        results.append({
            "sku": p.sku,
            "name": p.name,
            "category": p.category,
            "brand": p.brand,
            "vehicle_fitment": p.vehicle_fitment,
            "price": format_money(p.price),
            "stock": stock_qty,
            "description_snippet": snippet,
        })

    return results
