"""Protocol-level tests for deterministic recipe variant MCP tools."""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from cronometer_api_mcp import server

LB_10 = 4535.924
LB_11 = 4989.516


def _recipe(
    food_id: int,
    name: str,
    ingredients: list[dict],
    *,
    owner: int = 42,
    source: str = "Custom",
    cooked_weight: float | None = None,
) -> dict:
    raw_weight = sum(item["grams"] for item in ingredients)
    return {
        "id": food_id,
        "name": name,
        "owner": owner,
        "source": source,
        "comments": "base notes",
        "defaultMeasureId": 901,
        "ingredients": ingredients,
        "measures": [
            {
                "id": 901,
                "name": "Serving",
                "value": cooked_weight or raw_weight,
                "type": "Weight",
            },
            {
                "id": 902,
                "name": "full recipe",
                "value": cooked_weight or raw_weight,
                "type": "Weight",
            },
        ],
    }


BASE_RECIPE = _recipe(
    100,
    "Chicken Bowl_002",
    [
        {"foodId": 1, "measureId": 11, "grams": LB_10, "value": LB_10},
        {"foodId": 2, "measureId": 21, "grams": 150.0, "value": 150.0},
        {"foodId": 3, "measureId": 31, "grams": 1000.0, "value": 1000.0},
    ],
)


class FakeClient:
    def __init__(self) -> None:
        self.user_id = 42
        self.created: list[dict] = []
        self.foods = {100: BASE_RECIPE}
        self.search_results: list[dict] = []

    def get_food(self, food_id: int) -> dict:
        return self.foods[food_id]

    def search_food(self, query: str) -> list[dict]:
        return self.search_results

    def create_recipe(self, name: str, **kwargs) -> dict:
        self.created.append({"name": name, **kwargs})
        food_id = 9000 + len(self.created)
        self.foods[food_id] = _recipe(
            food_id,
            name,
            [
                {
                    "foodId": item[0],
                    "measureId": item[2] if len(item) == 3 else 0,
                    "grams": item[1],
                    "value": item[1],
                }
                for item in kwargs["ingredients"]
            ],
            cooked_weight=kwargs.get("cooked_weight_grams"),
        )
        self.search_results.append({"id": food_id, "name": name})
        result = {
            "food_id": food_id,
            "total_grams": sum(item[1] for item in kwargs["ingredients"]),
            "ingredient_count": len(kwargs["ingredients"]),
        }
        if kwargs.get("cooked_weight_grams") is not None:
            result["cooked_weight_grams"] = kwargs["cooked_weight_grams"]
        return result


def _call(monkeypatch, client: FakeClient, tool: str, **kwargs) -> dict:
    monkeypatch.setattr(server, "_get_client", lambda: client)
    response = getattr(server, tool)(**kwargs)
    return json.loads(response)


def _variant_args() -> dict:
    return {
        "base_recipe_id": 100,
        "anchor_food_ids": [1],
        "target_anchor_grams": LB_11,
        "fixed_food_ids": [2],
        "replacement_ingredients": [
            {"food_id": 1, "grams": 3000.0},
            {"food_id": 4, "grams": LB_11 - 3000.0},
        ],
    }


def test_preview_scales_anchor_substitution_and_keeps_onion_fixed(monkeypatch):
    client = FakeClient()
    client.search_results = [
        {"id": 201, "name": "Chicken Bowl_001"},
        {"id": 203, "name": "Chicken Bowl_003"},
        {"id": 210, "name": "Chicken Bowl_010"},
        {"id": 999, "name": "Chicken Bowl extra_999"},
    ]
    client.foods.update(
        {
            201: _recipe(201, "Chicken Bowl_001", BASE_RECIPE["ingredients"]),
            203: _recipe(203, "Chicken Bowl_003", BASE_RECIPE["ingredients"]),
            210: _recipe(210, "Chicken Bowl_010", BASE_RECIPE["ingredients"], owner=77),
            999: _recipe(999, "Chicken Bowl extra_999", BASE_RECIPE["ingredients"]),
        }
    )

    result = _call(monkeypatch, client, "preview_recipe_variant", **_variant_args())

    assert result["status"] == "success"
    assert result["proposed_name"] == "Chicken Bowl_004"
    assert result["scale_factor"] == pytest.approx(1.1)
    assert result["base_anchor_grams"] == LB_10
    assert result["target_anchor_grams"] == LB_11
    assert result["ingredients"] == [
        {"food_id": 1, "grams": 3000.0, "measure_id": None},
        {"food_id": 2, "grams": 150.0, "measure_id": 21},
        {"food_id": 3, "grams": 1100.0, "measure_id": 31},
        {"food_id": 4, "grams": 1989.516, "measure_id": None},
    ]
    assert result["raw_total_grams"] == pytest.approx(6239.516)
    assert result["duplicate"] is None
    assert "visible" in result["idempotency_scope"]
    assert client.created == []


def test_preview_rejects_replacement_total_that_misses_anchor(monkeypatch):
    client = FakeClient()
    args = _variant_args()
    args["replacement_ingredients"][1]["grams"] = 1000.0

    result = _call(monkeypatch, client, "preview_recipe_variant", **args)

    assert result["status"] == "error"
    assert "must total target_anchor_grams" in result["message"]
    assert client.created == []


def test_create_returns_visible_duplicate_without_write(monkeypatch):
    client = FakeClient()
    ingredients = [
        {"foodId": 1, "measureId": 0, "grams": 3000.0, "value": 3000.0},
        {"foodId": 2, "measureId": 21, "grams": 150.0, "value": 150.0},
        {"foodId": 3, "measureId": 31, "grams": 1100.0, "value": 1100.0},
        {"foodId": 4, "measureId": 0, "grams": 1989.516, "value": 1989.516},
    ]
    client.search_results = [{"id": 204, "name": "Chicken Bowl_004"}]
    client.foods[204] = _recipe(204, "Chicken Bowl_004", ingredients)

    result = _call(monkeypatch, client, "create_recipe_variant", **_variant_args())

    assert result["status"] == "success"
    assert result["created"] is False
    assert result["duplicate"] == {"food_id": 204, "name": "Chicken Bowl_004"}
    assert client.created == []


def test_create_cooked_variant_writes_new_version_and_returns_share_info(monkeypatch):
    client = FakeClient()
    args = _variant_args()
    args["cooked_weight_grams"] = 5000.0

    result = _call(monkeypatch, client, "create_recipe_variant", **args)

    assert result["status"] == "success"
    assert result["created"] is True
    assert result["name"] == "Chicken Bowl_003"
    assert result["raw_total_grams"] == pytest.approx(6239.516)
    assert result["cooked_weight_grams"] == 5000.0
    assert client.created[0]["cooked_weight_grams"] == 5000.0
    assert client.created[0]["ingredients"] == [
        (1, 3000.0),
        (2, 150.0, 21),
        (3, 1100.0, 31),
        (4, 1989.516),
    ]
    assert result["sharing"]["writes_performed"] is False
    assert "Gold" in result["sharing"]["requirement"]
    assert "Chicken Bowl_003" in result["sharing"]["friend_action"]


def test_post_cooking_yield_is_a_distinct_immutable_version(monkeypatch):
    client = FakeClient()
    client.search_results = [{"id": 200, "name": "Chicken Bowl_001"}]
    client.foods[200] = _recipe(
        200,
        "Chicken Bowl_001",
        BASE_RECIPE["ingredients"],
    )

    result = _call(
        monkeypatch,
        client,
        "create_recipe_variant",
        base_recipe_id=100,
        cooked_weight_grams=5000.0,
    )

    assert result["created"] is True
    assert result["name"] == "Chicken Bowl_003"
    assert client.created[0]["name"] == "Chicken Bowl_003"
    assert client.created[0]["ingredients"] == [
        (1, LB_10, 11),
        (2, 150.0, 21),
        (3, 1000.0, 31),
    ]


def test_share_info_is_read_only_and_names_exact_recipe(monkeypatch):
    client = FakeClient()

    result = _call(monkeypatch, client, "get_recipe_share_info", recipe_id=100)

    assert result["status"] == "success"
    assert result["food_id"] == 100
    assert result["name"] == "Chicken Bowl_002"
    assert result["sharing"]["writes_performed"] is False
    assert result["sharing"]["friend_action"].endswith("'Chicken Bowl_002'.")


def test_base_food_must_be_a_recipe(monkeypatch):
    client = FakeClient()
    client.foods[100] = {
        "id": 100,
        "name": "Not a recipe",
        "source": "Custom",
        "owner": 42,
    }

    result = _call(
        monkeypatch,
        client,
        "preview_recipe_variant",
        base_recipe_id=100,
    )

    assert result["status"] == "error"
    assert "not a recipe" in result["message"].lower()


def test_direct_recipe_upload_supports_exact_overrides(monkeypatch):
    client = FakeClient()

    result = _call(
        monkeypatch,
        client,
        "create_recipe_variant",
        base_name="Notion Chicken",
        ingredients=[
            {"food_id": 1, "grams": 1000.0},
            {"food_id": 2, "grams": 150.0, "measure_id": 21},
        ],
        overrides=[
            {"food_id": 1, "grams": 1100.0},
            {"food_id": 3, "grams": 25.0},
        ],
    )

    assert result["created"] is True
    assert result["name"] == "Notion Chicken_001"
    assert client.created[0]["ingredients"] == [
        (1, 1100.0),
        (2, 150.0, 21),
        (3, 25.0),
    ]


def test_concurrent_same_process_retries_create_once(monkeypatch):
    client = FakeClient()
    monkeypatch.setattr(server, "_get_client", lambda: client)

    def create() -> dict:
        return json.loads(server.create_recipe_variant(**_variant_args()))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: create(), range(8)))

    assert sum(result["created"] for result in results) == 1
    assert len(client.created) == 1
    assert {result["food_id"] for result in results} == {9001}
