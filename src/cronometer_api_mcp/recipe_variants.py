"""Deterministic recipe scaling, identity, and visible-version discovery."""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Protocol

MILLIGRAMS_PER_GRAM = 1000
MAX_VERSION = 999
IDEMPOTENCY_SCOPE = (
    "Duplicate prevention covers owned Custom recipe variants visible in the "
    "current Cronometer search response within this MCP server process. Search "
    "result limits and separate MCP processes are outside the guarantee."
)


class RecipeClient(Protocol):
    @property
    def user_id(self) -> int: ...

    def get_food(self, food_id: int) -> dict: ...

    def search_food(self, query: str) -> list[dict]: ...


def _positive_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be a positive number")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{label} must be a positive number")
    return number


def _food_id(value: object, label: str = "food_id") -> int:
    if isinstance(value, bool):
        raise TypeError(f"{label} must be a positive integer")
    try:
        result = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a positive integer") from exc
    if result <= 0 or result != value:
        raise ValueError(f"{label} must be a positive integer")
    return result


def normalize_ingredients(
    ingredients: list[dict], *, recipe_rows: bool = False
) -> list[dict]:
    """Validate, aggregate, milligram-round, and sort ingredient rows."""
    if not isinstance(ingredients, list) or not ingredients:
        raise ValueError("A recipe requires at least one ingredient")

    merged: dict[int, dict] = {}
    id_key = "foodId" if recipe_rows else "food_id"
    measure_key = "measureId" if recipe_rows else "measure_id"
    for index, item in enumerate(ingredients):
        if not isinstance(item, dict):
            raise TypeError(f"Ingredient {index} must be an object")
        if id_key not in item or "grams" not in item:
            raise ValueError(f"Ingredient {index} requires '{id_key}' and 'grams'")
        food_id = _food_id(item[id_key], f"ingredient {index} {id_key}")
        grams = _positive_number(item["grams"], f"ingredient {food_id} grams")
        measure_value = item.get(measure_key)
        measure_id = None
        if measure_value not in (None, 0):
            measure_id = _food_id(measure_value, f"ingredient {food_id} {measure_key}")

        current = merged.get(food_id)
        if current is None:
            merged[food_id] = {
                "food_id": food_id,
                "grams": grams,
                "measure_id": measure_id,
            }
            continue
        if (
            current["measure_id"] is not None
            and measure_id is not None
            and current["measure_id"] != measure_id
        ):
            raise ValueError(f"Ingredient {food_id} has conflicting measure_id values")
        current["grams"] += grams
        current["measure_id"] = current["measure_id"] or measure_id

    normalized = []
    for food_id in sorted(merged):
        item = merged[food_id]
        grams = round(item["grams"] * MILLIGRAMS_PER_GRAM) / MILLIGRAMS_PER_GRAM
        if grams <= 0:
            raise ValueError(f"Ingredient {food_id} rounds to zero grams")
        normalized.append({**item, "grams": grams})
    return normalized


def recipe_stem(name: str) -> str:
    """Return a trimmed recipe name without one trailing `_NNN` suffix."""
    if not isinstance(name, str) or not name.strip():
        raise ValueError("base_name must not be blank")
    stem = re.sub(r"_[0-9]{3}$", "", name.strip())
    if not stem:
        raise ValueError("base_name must contain text before a version suffix")
    return stem


def extract_recipe(food: dict) -> dict:
    """Extract strict variant inputs and effective yield from a full food record."""
    if not isinstance(food, dict):
        raise TypeError("Cronometer returned a malformed food record")
    name = food.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValueError("Cronometer food record has no valid name")
    rows = food.get("ingredients")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"Cronometer food '{name}' is not a recipe")
    ingredients = normalize_ingredients(rows, recipe_rows=True)
    raw_total = round(sum(item["grams"] for item in ingredients), 3)

    full_recipe_measures = [
        measure
        for measure in food.get("measures", [])
        if isinstance(measure, dict)
        and isinstance(measure.get("name"), str)
        and measure["name"].strip().casefold() == "full recipe"
    ]
    if len(full_recipe_measures) != 1:
        raise ValueError(
            f"Cronometer recipe '{name}' must have exactly one full recipe measure"
        )
    effective_yield = _positive_number(
        full_recipe_measures[0].get("value"),
        f"Cronometer recipe '{name}' full recipe measure",
    )
    return {
        "food_id": food.get("id"),
        "name": name.strip(),
        "ingredients": ingredients,
        "raw_total_grams": raw_total,
        "effective_yield_grams": round(effective_yield, 3),
        "comments": food.get("comments")
        if isinstance(food.get("comments"), str)
        else None,
    }


def recipe_fingerprint(ingredients: list[dict], effective_yield_grams: float) -> str:
    """Hash nutrition-affecting recipe state using integer milligrams."""
    normalized = normalize_ingredients(ingredients)
    canonical = {
        "ingredient_milligrams": [
            [item["food_id"], round(item["grams"] * MILLIGRAMS_PER_GRAM)]
            for item in normalized
        ],
        "yield_milligrams": round(
            _positive_number(effective_yield_grams, "effective_yield_grams")
            * MILLIGRAMS_PER_GRAM
        ),
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def build_variant(
    ingredients: list[dict],
    *,
    anchor_food_ids: list[int] | None = None,
    target_anchor_grams: float | None = None,
    fixed_food_ids: list[int] | None = None,
    replacement_ingredients: list[dict] | None = None,
    overrides: list[dict] | None = None,
    cooked_weight_grams: float | None = None,
) -> dict:
    """Apply proportional scaling, fixed rows, substitutions, and overrides."""
    base = normalize_ingredients(ingredients)
    base_by_id = {item["food_id"]: item for item in base}
    fixed = {_food_id(value, "fixed_food_id") for value in fixed_food_ids or []}
    anchors = {_food_id(value, "anchor_food_id") for value in anchor_food_ids or []}

    unknown_fixed = fixed - base_by_id.keys()
    unknown_anchors = anchors - base_by_id.keys()
    if unknown_fixed:
        raise ValueError(
            f"fixed_food_ids are not in the recipe: {sorted(unknown_fixed)}"
        )
    if unknown_anchors:
        raise ValueError(
            f"anchor_food_ids are not in the recipe: {sorted(unknown_anchors)}"
        )
    if fixed & anchors:
        raise ValueError("An anchor ingredient cannot also be fixed")

    if target_anchor_grams is None:
        if anchors or replacement_ingredients is not None:
            raise ValueError(
                "target_anchor_grams is required with anchor_food_ids or "
                "replacement_ingredients"
            )
        base_anchor_grams = None
        target = None
        scale_factor = 1.0
    else:
        target = _positive_number(target_anchor_grams, "target_anchor_grams")
        if not anchors:
            raise ValueError(
                "anchor_food_ids is required when target_anchor_grams is set"
            )
        base_anchor_grams = sum(base_by_id[food_id]["grams"] for food_id in anchors)
        scale_factor = target / base_anchor_grams

    scaled = []
    for item in base:
        grams = (
            item["grams"] if item["food_id"] in fixed else item["grams"] * scale_factor
        )
        scaled.append({**item, "grams": grams})

    if replacement_ingredients is not None:
        replacements = normalize_ingredients(replacement_ingredients)
        replacement_total = sum(item["grams"] for item in replacements)
        assert target is not None
        if abs(replacement_total - target) >= 0.0005:
            raise ValueError(
                "replacement_ingredients must total target_anchor_grams "
                f"({replacement_total:.3f}g != {target:.3f}g)"
            )
        scaled = [item for item in scaled if item["food_id"] not in anchors]
        scaled.extend(replacements)

    if overrides:
        override_rows = normalize_ingredients(overrides)
        override_by_id = {item["food_id"]: item for item in override_rows}
        scaled = [override_by_id.pop(item["food_id"], item) for item in scaled]
        scaled.extend(override_by_id.values())

    final_ingredients = normalize_ingredients(scaled)
    raw_total = round(sum(item["grams"] for item in final_ingredients), 3)
    cooked = (
        None
        if cooked_weight_grams is None
        else round(_positive_number(cooked_weight_grams, "cooked_weight_grams"), 3)
    )
    effective_yield = raw_total if cooked is None else cooked
    return {
        "ingredients": final_ingredients,
        "base_anchor_grams": None
        if base_anchor_grams is None
        else round(base_anchor_grams, 3),
        "target_anchor_grams": None if target is None else round(target, 3),
        "scale_factor": scale_factor,
        "raw_total_grams": raw_total,
        "cooked_weight_grams": cooked,
        "effective_yield_grams": effective_yield,
        "fingerprint": recipe_fingerprint(final_ingredients, effective_yield),
    }


def _owner_id(owner: object) -> int | None:
    if isinstance(owner, int) and not isinstance(owner, bool):
        return owner
    if isinstance(owner, dict):
        for key in ("id", "userId"):
            value = owner.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                return value
    return None


def discover_owned_versions(
    client: RecipeClient,
    base_name: str,
    fingerprint: str,
    *,
    known_foods: list[dict] | None = None,
) -> dict:
    """Inspect exact owned variants in the current Cronometer search response."""
    stem = recipe_stem(base_name)
    pattern = re.compile(rf"^{re.escape(stem)}_([0-9]{{3}})$")
    hits = client.search_food(stem)
    if not isinstance(hits, list):
        raise TypeError("Cronometer search returned a malformed response")

    candidates = []
    seen_ids: set[int] = set()
    foods_to_check = list(known_foods or [])
    for hit in hits:
        if not isinstance(hit, dict) or not pattern.fullmatch(str(hit.get("name", ""))):
            continue
        food_id = _food_id(hit.get("id"), "search result food id")
        if food_id in seen_ids:
            continue
        seen_ids.add(food_id)
        foods_to_check.append(client.get_food(food_id))

    seen_ids.clear()
    for food in foods_to_check:
        if not isinstance(food, dict):
            raise TypeError("Cronometer returned a malformed food record")
        food_id = _food_id(food.get("id"), "recipe food id")
        if food_id in seen_ids:
            continue
        seen_ids.add(food_id)
        name = food.get("name") if isinstance(food, dict) else None
        match = pattern.fullmatch(name.strip()) if isinstance(name, str) else None
        if not match:
            continue
        if (
            food.get("source") != "Custom"
            or _owner_id(food.get("owner")) != client.user_id
        ):
            continue
        recipe = extract_recipe(food)
        candidate_fingerprint = recipe_fingerprint(
            recipe["ingredients"], recipe["effective_yield_grams"]
        )
        candidates.append(
            {
                "food_id": food_id,
                "name": recipe["name"],
                "version": int(match.group(1)),
                "fingerprint": candidate_fingerprint,
            }
        )

    candidates.sort(key=lambda item: (item["version"], item["food_id"]))
    duplicate = next(
        (
            {"food_id": item["food_id"], "name": item["name"]}
            for item in candidates
            if item["fingerprint"] == fingerprint
        ),
        None,
    )
    if duplicate is not None:
        proposed_name = duplicate["name"]
    else:
        next_version = max((item["version"] for item in candidates), default=0) + 1
        if next_version > MAX_VERSION:
            raise ValueError(
                f"Recipe stem '{stem}' has reached version _{MAX_VERSION:03d}"
            )
        proposed_name = f"{stem}_{next_version:03d}"
    return {
        "proposed_name": proposed_name,
        "duplicate": duplicate,
        "visible_owned_versions": len(candidates),
    }


def sharing_info(name: str) -> dict:
    """Describe Cronometer's account-level recipe sharing behavior honestly."""
    return {
        "mode": "account-level friend sharing",
        "writes_performed": False,
        "requirement": (
            "Cronometer Gold and an accepted friend connection configured in "
            "Cronometer under More > Sharing > Friends."
        ),
        "friend_action": f"In Add Food, search for the exact recipe name '{name}'.",
        "privacy": "Friend sharing exposes custom foods and recipes, not the diary.",
    }
