# cronometer-api-mcp

<!-- mcp-name: io.github.rwestergren/cronometer-api-mcp -->

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/rwestergren/cronometer-api-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/rwestergren/cronometer-api-mcp/actions/workflows/ci.yml)
[![Build Docker image](https://github.com/rwestergren/cronometer-api-mcp/actions/workflows/docker.yml/badge.svg)](https://github.com/rwestergren/cronometer-api-mcp/actions/workflows/docker.yml)
[![PyPI](https://img.shields.io/pypi/v/cronometer-api-mcp.svg)](https://pypi.org/project/cronometer-api-mcp/)

> **Hosted version for Claude.ai, ChatGPT, and Grok coming soon.** [**Join the waitlist →**](https://tally.so/r/A7WVge?ref=cronometer-api-mcp)

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server for [Cronometer](https://cronometer.com/) nutrition tracking, built on the reverse-engineered mobile REST API.

Unlike [cronometer-mcp](https://github.com/cphoskins/cronometer-mcp), which takes a comprehensive GWT-RPC approach against Cronometer's web backend, this server talks to the same JSON REST API used by the Cronometer Android app -- with clean payloads and stable, versioned endpoints.

## Features

- **Food log** -- diary entries with food names, amounts, meal groups
- **Nutrition data** -- daily macro/micro totals and nutrition scores with per-nutrient confidence
- **Food search** -- search the Cronometer food database, get detailed nutrition info
- **Diary management** -- add/remove entries, copy days, mark days complete
- **Custom foods** -- create foods with custom nutrition data
- **Recipe variants** -- preview and create immutable, proportionally scaled recipes with substitutions, cooked yield, version allocation, and duplicate protection
- **Macro targets** -- read weekly schedule and saved templates
- **Fasting** -- view history and aggregate statistics
- **Biometrics** -- weight, body fat, heart rate, and other tracked metrics over a date range

## Quick Start

### 1. Install [uv](https://docs.astral.sh/uv/)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Set credentials

```bash
export CRONOMETER_USERNAME="your@email.com"
export CRONOMETER_PASSWORD="your-password"
```

#### Optional: two-factor authentication

If the account has two-factor authentication enabled, `/api/v2/login`
answers `TOTP_CODE_REQUIRED` unless the request carries the current 6-digit
code. Give the server the base32 key that Cronometer showed when 2FA was set
up (the same key you scanned into your authenticator app) and it derives the
code itself at every login (RFC 6238, SHA-1, 30 s period):

```bash
export CRONOMETER_TOTP_SECRET="ABCD EFGH IJKL MNOP QRST UVWX YZ23 4567"
```

Spaces and lowercase are fine. Leave it unset for accounts without 2FA.

#### Optional: override the account timezone

Diary entries are stamped in your Cronometer account's timezone, which the
server reports at login. If that zone is wrong (for example, an older build
had reset it) you can force a specific IANA zone without changing your account
settings:

```bash
export CRONOMETER_ACCOUNT_TZ="America/Los_Angeles"
```

When set, this takes precedence over both the value reported at login and any
cached session, so it also overrides a stale cached timezone.

### 3. Configure your MCP client

`uvx` downloads and runs the server on demand -- no separate install step.

#### OpenCode (`opencode.json`)

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "cronometer": {
      "type": "local",
      "command": ["uvx", "cronometer-api-mcp"],
      "environment": {
        "CRONOMETER_USERNAME": "{env:CRONOMETER_USERNAME}",
        "CRONOMETER_PASSWORD": "{env:CRONOMETER_PASSWORD}",
        "CRONOMETER_TOTP_SECRET": "{env:CRONOMETER_TOTP_SECRET}",
        "CRONOMETER_ACCOUNT_TZ": "{env:CRONOMETER_ACCOUNT_TZ}"
      },
      "enabled": true
    }
  }
}
```

#### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "cronometer": {
      "command": "uvx",
      "args": ["cronometer-api-mcp"],
      "env": {
        "CRONOMETER_USERNAME": "your@email.com",
        "CRONOMETER_PASSWORD": "your-password",
        "CRONOMETER_TOTP_SECRET": "your-base32-key",
        "CRONOMETER_ACCOUNT_TZ": "America/Los_Angeles"
      }
    }
  }
}
```

## Available Tools

### Food Log & Nutrition

| Tool | Description |
|------|-------------|
| `get_food_log` | Diary entries for a date, each enriched with food name, source, serving measure/count, and that food's per-entry nutrient contribution, plus an energy_summary (target/consumed/remaining kcal) and a nutrition_summary of consumed totals for every tracked nutrient |
| `get_daily_nutrition` | Consumed macro and micronutrient totals for every nutrient tracked in Cronometer |
| `get_nutrition_scores` | Category scores (Vitamins, Minerals, etc.) with per-nutrient consumed amounts and confidence levels |

### Food Search & Details

| Tool | Description |
|------|-------------|
| `search_foods` | Search the Cronometer food database by name |
| `get_food_details` | Full nutrition profile and serving sizes for a food |

### Diary Management

| Tool | Description |
|------|-------------|
| `add_food_entry` | Log a food serving to the diary |
| `remove_food_entry` | Remove one or more diary entries |
| `add_custom_food` | Create a custom food with specified nutrition |
| `add_recipe` | Create a recipe from existing foods referenced by ID and gram weight |
| `import_recipe` | Create a recipe from a free-text ingredient list; Cronometer matches each line to a database food and converts the amount to grams |
| `preview_recipe_variant` | Preview scaling, fixed ingredients, substitutions, exact overrides, cooked yield, the next visible owned `_NNN` version, and any visible duplicate without writing |
| `create_recipe_variant` | Create an immutable versioned recipe, or return a matching visible owned variant without another write |
| `get_recipe_share_info` | Return the exact-name workflow and Gold/friend prerequisites for Cronometer's account-level recipe sharing; performs no sharing write |
| `copy_day` | Copy all entries from the previous day |
| `mark_day_complete` | Mark a diary day as complete or incomplete |

### Targets & Tracking

| Tool | Description |
|------|-------------|
| `get_macro_targets` | Weekly macro schedule and saved target templates |
| `get_fasting_history` | Fasting history within a date range |
| `get_fasting_stats` | Aggregate fasting statistics |
| `list_biometrics` | List trackable biometric metrics and their units |
| `get_biometrics` | Biometric time series (e.g. weight, body fat) within a date range |

All date parameters use `YYYY-MM-DD` format and default to today when omitted.

## Versioned Recipe Workflow

Spoken requests and Notion pages are intentionally handled by the MCP client
(for example, Codex), where transcription and page access already live. The
client resolves each ingredient with `search_foods`, converts the recipe into
exact food IDs and gram weights, then sends the same structured arguments first
to `preview_recipe_variant` and—after review—to `create_recipe_variant`.

For example, suppose recipe `84201` contains 10 lb (4535.924 g) of chicken,
rice, spices, and one 150 g onion. This preview changes the chicken anchor to
11 lb, keeps the onion fixed, scales the remaining ingredients by 1.1, and
replaces the chicken with an exact breast/thigh split:

```json
{
  "base_recipe_id": 84201,
  "anchor_food_ids": [111],
  "target_anchor_grams": 4989.516,
  "fixed_food_ids": [222],
  "replacement_ingredients": [
    {"food_id": 111, "grams": 3000.0},
    {"food_id": 333, "grams": 1989.516}
  ],
  "overrides": []
}
```

Use those arguments with `preview_recipe_variant`. Its response contains the
final ingredient rows, raw total, scale factor, proposed name such as
`Chicken Bowl_004`, and duplicate status. Send the same values to
`create_recipe_variant` to save the recipe. Initial uploads use `base_name` and
`ingredients` instead of `base_recipe_id`; `overrides` can set or add any exact
final ingredient weight.

Recipe edits never mutate prior versions or diary history. A post-cooking yield
is another immutable version: call the preview/create pair with the prior
`base_recipe_id` and `cooked_weight_grams`. Raw ingredient rows remain intact,
non-water batch nutrients are conserved, and the weight difference is applied
to water as [Cronometer documents](https://support.cronometer.com/hc/en-us/articles/4406291608724-Set-Cooked-Recipe-Weight).
A changed yield fails before the recipe write if the ingredients do not contain
water data or the loss exceeds tracked water.

Version discovery and duplicate protection are deliberately bounded. They cover
owned Custom recipe variants visible in the current Cronometer search response,
and concurrent calls are serialized within one MCP server process. Cronometer
does not document search result completeness, and separate MCP processes do not
share a lock, so the tool response repeats this limitation.

Cronometer Gold [friend sharing](https://support.cronometer.com/hc/en-us/articles/360018867471-Sharing)
is account-level, not a per-recipe API write.
After friends are connected under **More > Sharing > Friends**, they can find a
completed recipe by its exact versioned name in **Add Food**.

## Transport

stdio only. For remote/hosted use, the stdio server is wrapped by
[supergateway](https://github.com/supercorp-ai/supergateway) (see `Dockerfile`),
which owns the HTTP listener and exposes MCP streamable-HTTP at `/mcp`. The
server has **no built-in authentication** — any remote deployment must sit
behind an authenticating gateway or reverse proxy.

## Development

For local development, copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
# edit .env
uv run cronometer-api-mcp
```

The CLI auto-loads `.env` on startup (dev convenience only). Real environment variables always win over `.env`, so production deployments and MCP client `env` blocks are unaffected.

## How It Works

This server communicates with `mobile.cronometer.com` -- the same REST API used by the Cronometer Android/Flutter app. The API was reverse-engineered through:

1. Static analysis of `libapp.so` (Dart AOT snapshot) from the APK to discover endpoint names
2. Traffic interception via Frida + mitmproxy to capture exact request/response formats
3. Trial-and-error against the live API to confirm payload shapes

The API uses two protocols:

- **v2 (`POST /api/v2/*`)** -- JSON-body auth, used for most operations (food search, diary read/write, nutrition, fasting, macros, biometrics)
- **v3 (`DELETE /api/v3/user/{id}/*`)** -- Header-based auth (`x-crono-session`), used for diary entry deletion

Recipe import is the one asynchronous operation: `import_recipe` returns a job id, and `poll_async_result` is polled until the server reports 100% progress and attaches the parsed ingredients.

## Python API

You can use the client directly:

```python
from cronometer_api_mcp.client import CronometerClient
from datetime import date

client = CronometerClient()

# Search for foods
results = client.search_food("chicken breast")

# Get food details
food = client.get_food(results[0]["id"])

# Log a serving
client.add_serving(
    food_id=food["id"],
    measure_id=food["defaultMeasureId"],
    grams=200,
)

# Get today's diary
diary = client.get_diary()

# Import a recipe from a free-text ingredient list
recipe = client.import_recipe("one hot dog\nketchup\nbun")
print(recipe["food_id"], recipe["ingredients"])

# Parse without saving, to review the matches first
preview = client.import_recipe("2 tbsp olive oil\n200g chicken", save=False)

# Create a weight-based recipe whose finished batch weighs 850 g. The client
# retains the raw ingredient rows and applies the weight difference to water.
cooked = client.create_recipe(
    "Chicken Bowl_004",
    ingredients=[(111, 700.0), (222, 200.0)],
    cooked_weight_grams=850.0,
)

# Get nutrition scores
scores = client.get_nutrition_scores()
```

## License

MIT
