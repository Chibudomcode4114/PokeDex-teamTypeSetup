"""Deterministic normalization of raw PokeAPI responses into game-specific data structures.

This module is strictly isolated from HTTP transports and database persistence layers.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.adapters.pokeapi.exceptions import PokeApiNormalizationError
from app.adapters.pokeapi.schemas import (
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
    TargetGameContext,
    get_target_game_context,
)

logger = logging.getLogger(__name__)

GENERATION_ROMAN_MAP: dict[str, int] = {
    "generation-i": 1,
    "generation-ii": 2,
    "generation-iii": 3,
    "generation-iv": 4,
    "generation-v": 5,
    "generation-vi": 6,
    "generation-vii": 7,
    "generation-viii": 8,
    "generation-ix": 9,
}

REQUIRED_BATTLE_STATS: set[str] = {
    "hp",
    "attack",
    "defense",
    "special-attack",
    "special-defense",
    "speed",
}


class PokeApiNormalizer:
    """Pure normalizer that transforms raw PokeAPI responses into game-specific domain data.

    This service performs no I/O, no network calls, and no database writes.
    """

    @classmethod
    def parse_generation_number(cls, gen_ref: dict[str, Any] | str | None) -> int | None:
        """Parse the integer generation number from a PokeAPI generation resource reference."""
        if not gen_ref:
            return None

        name = ""
        url = ""
        if isinstance(gen_ref, dict):
            name = str(gen_ref.get("name", "")).strip().lower()
            url = str(gen_ref.get("url", "")).strip()
        else:
            name = str(gen_ref).strip().lower()

        if name in GENERATION_ROMAN_MAP:
            return GENERATION_ROMAN_MAP[name]

        # Fallback: extract trailing numeric ID from URL e.g. .../generation/3/
        match = re.search(r"/generation/(\d+)/?", url)
        if match:
            return int(match.group(1))

        return None

    @classmethod
    def normalize_pokemon(
        cls,
        pokemon_payload: dict[str, Any],
        species_payload: dict[str, Any],
        target_game: TargetGameContext | str,
    ) -> NormalizedPokemon:
        """Normalize raw Pokemon and PokemonSpecies payloads for a specific target game context.

        Args:
            pokemon_payload: Raw JSON dictionary from /pokemon/{id_or_name}.
            species_payload: Raw JSON dictionary from /pokemon-species/{id_or_name}.
            target_game: Explicit TargetGameContext or string game identifier (e.g. 'firered').

        Returns:
            NormalizedPokemon data structure containing game-resolved identity, types,
            abilities, stats, and availability.

        Raises:
            PokeApiNormalizationError: If required payload fields are missing, malformed,
            or internally inconsistent.
        """
        # 1. Resolve Target Game Context
        if isinstance(target_game, str):
            try:
                context = get_target_game_context(target_game)
            except ValueError as e:
                raise PokeApiNormalizationError(str(e)) from e
        elif isinstance(target_game, TargetGameContext):
            context = target_game
        else:
            raise PokeApiNormalizationError(
                f"Invalid target_game type: {type(target_game)}. Must be TargetGameContext or str."
            )

        # 2. Validate Root Payload Structures
        if not isinstance(pokemon_payload, dict) or not isinstance(species_payload, dict):
            raise PokeApiNormalizationError(
                "Both pokemon_payload and species_payload must be dicts."
            )

        if not pokemon_payload.get("name"):
            raise PokeApiNormalizationError("pokemon_payload missing required 'name' field.")
        if not species_payload.get("name"):
            raise PokeApiNormalizationError("species_payload missing required 'name' field.")

        pokemon_slug = str(pokemon_payload["name"]).strip().lower()
        species_slug = str(species_payload["name"]).strip().lower()
        is_default = bool(pokemon_payload.get("is_default", True))

        # 3. Resolve Identity & Form
        dex_number = cls._resolve_national_dex_number(species_payload)

        if is_default:
            form_name = None
            internal_id = species_slug
        else:
            if pokemon_slug.startswith(f"{species_slug}-"):
                form_name = pokemon_slug[len(species_slug) + 1 :]
            else:
                form_name = pokemon_slug
            internal_id = pokemon_slug

        display_name = cls._resolve_display_name(species_payload, species_slug, form_name)

        # 4. Resolve Game Availability
        # Availability Policy: compatible/present in ROM data context for the target version
        game_indices = pokemon_payload.get("game_indices", [])
        if not isinstance(game_indices, list):
            raise PokeApiNormalizationError("'game_indices' in pokemon_payload must be a list.")

        target_version_slug = context.version_name.strip().lower()
        is_available = any(
            str(idx.get("version", {}).get("name", "")).strip().lower() == target_version_slug
            for idx in game_indices
            if isinstance(idx, dict)
        )

        # 5. Resolve Historical Types
        types = cls._resolve_historical_types(pokemon_payload, context.generation)

        # 6. Resolve Historical Abilities
        abilities = cls._resolve_historical_abilities(pokemon_payload, context.generation)

        # 7. Resolve Historical Base Stats
        base_stats = cls._resolve_historical_base_stats(pokemon_payload, context.generation)

        return NormalizedPokemon(
            id=internal_id,
            dex_number=dex_number,
            name=display_name,
            slug=pokemon_slug,
            species_name=species_slug,
            form_name=form_name,
            is_default=is_default,
            game_id=context.game_id,
            is_available=is_available,
            types=types,
            abilities=abilities,
            base_stats=base_stats,
        )

    @classmethod
    def _resolve_national_dex_number(cls, species_payload: dict[str, Any]) -> int:
        """Resolve the official National Pokédex number from species metadata."""
        pokedex_numbers = species_payload.get("pokedex_numbers", [])
        if isinstance(pokedex_numbers, list):
            for entry in pokedex_numbers:
                if (
                    isinstance(entry, dict)
                    and entry.get("pokedex", {}).get("name") == "national"
                    and entry.get("entry_number") is not None
                ):
                    return int(entry["entry_number"])

        # Fallback to species numeric id
        species_id = species_payload.get("id")
        if species_id is not None:
            return int(species_id)

        raise PokeApiNormalizationError(
            "Could not resolve National Dex number from species_payload."
        )

    @classmethod
    def _resolve_display_name(
        cls,
        species_payload: dict[str, Any],
        species_slug: str,
        form_name: str | None,
    ) -> str:
        """Resolve localized English display name with form qualification if applicable."""
        names_list = species_payload.get("names", [])
        english_name: str | None = None

        if isinstance(names_list, list):
            for n in names_list:
                if (
                    isinstance(n, dict)
                    and n.get("language", {}).get("name") == "en"
                    and n.get("name")
                ):
                    english_name = str(n["name"])
                    break

        base_name = english_name or species_slug.replace("-", " ").title()

        if form_name:
            formatted_form = form_name.replace("-", " ").title()
            return f"{base_name} ({formatted_form})"
        return base_name

    @classmethod
    def _resolve_historical_types(
        cls,
        pokemon_payload: dict[str, Any],
        target_generation: int,
    ) -> tuple[NormalizedTypeAssignment, ...]:
        """Resolve the active elemental typing for the target generation.

        PokeAPI past_types generation N means the LAST generation in which that listed
        typing applied. For target generation G, select the past_types entry with
        the smallest N >= G, otherwise fall back to current types.
        """
        past_types = pokemon_payload.get("past_types", [])
        if not isinstance(past_types, list):
            raise PokeApiNormalizationError("'past_types' must be a list.")

        applicable_past_entries: list[tuple[int, list[dict[str, Any]]]] = []
        for entry in past_types:
            if not isinstance(entry, dict):
                continue
            gen_number = cls.parse_generation_number(entry.get("generation"))
            if gen_number is None:
                raise PokeApiNormalizationError(
                    f"Malformed generation reference in past_types: {entry.get('generation')}"
                )
            if gen_number >= target_generation:
                raw_type_list = entry.get("types", [])
                if not isinstance(raw_type_list, list):
                    raise PokeApiNormalizationError("Types in past_types entry must be a list.")
                applicable_past_entries.append((gen_number, raw_type_list))

        if applicable_past_entries:
            # Pick entry with the smallest boundary N >= target_generation
            applicable_past_entries.sort(key=lambda item: item[0])
            chosen_types = applicable_past_entries[0][1]
        else:
            chosen_types = pokemon_payload.get("types", [])
            if not isinstance(chosen_types, list):
                raise PokeApiNormalizationError("'types' in pokemon_payload must be a list.")

        if not chosen_types:
            raise PokeApiNormalizationError("Pokemon payload contains no valid types.")

        normalized_assignments: list[NormalizedTypeAssignment] = []
        for t in chosen_types:
            if not isinstance(t, dict):
                continue
            slot = t.get("slot")
            type_obj = t.get("type", {})
            type_name = type_obj.get("name") if isinstance(type_obj, dict) else None

            if slot is None or not type_name:
                raise PokeApiNormalizationError(
                    f"Malformed type item: slot={slot}, type_name={type_name}"
                )

            normalized_assignments.append(
                NormalizedTypeAssignment(
                    slot=int(slot),
                    type_id=str(type_name).strip().lower(),
                )
            )

        # Preserve slot ordering (slot 1 then slot 2)
        normalized_assignments.sort(key=lambda a: a.slot)
        return tuple(normalized_assignments)

    @classmethod
    def _resolve_historical_abilities(
        cls,
        pokemon_payload: dict[str, Any],
        target_generation: int,
    ) -> tuple[NormalizedAbilityAssignment, ...]:
        """Resolve active abilities by slot for the target generation.

        Starts with current abilities. Applies past_abilities overrides where generation N >= G.
        A past ability entry with ability = null means that slot did not exist in that historical
        context and is removed.

        For Generation III (G = 3), hidden abilities did not exist and are excluded.
        """
        current_abilities_list = pokemon_payload.get("abilities", [])
        if not isinstance(current_abilities_list, list):
            raise PokeApiNormalizationError("'abilities' in pokemon_payload must be a list.")

        abilities_by_slot: dict[int, dict[str, Any]] = {}
        for item in current_abilities_list:
            if not isinstance(item, dict):
                continue
            slot = item.get("slot")
            is_hidden = bool(item.get("is_hidden", False))
            ability_obj = item.get("ability", {})
            ability_name = ability_obj.get("name") if isinstance(ability_obj, dict) else None

            if slot is None or not ability_name:
                raise PokeApiNormalizationError(
                    f"Malformed ability item: slot={slot}, ability_name={ability_name}"
                )

            abilities_by_slot[int(slot)] = {
                "slot": int(slot),
                "ability_id": str(ability_name).strip().lower(),
                "is_hidden": is_hidden,
            }

        past_abilities = pokemon_payload.get("past_abilities", [])
        if not isinstance(past_abilities, list):
            raise PokeApiNormalizationError("'past_abilities' must be a list.")

        applicable_past_entries: list[tuple[int, list[dict[str, Any]]]] = []
        for entry in past_abilities:
            if not isinstance(entry, dict):
                continue
            gen_number = cls.parse_generation_number(entry.get("generation"))
            if gen_number is None:
                raise PokeApiNormalizationError(
                    f"Malformed generation reference in past_abilities: {entry.get('generation')}"
                )
            if gen_number >= target_generation:
                raw_ability_list = entry.get("abilities", [])
                if not isinstance(raw_ability_list, list):
                    raise PokeApiNormalizationError("Abilities in past_abilities must be a list.")
                applicable_past_entries.append((gen_number, raw_ability_list))

        # Sort descending (chronologically reverse: newer past states applied before older ones)
        applicable_past_entries.sort(key=lambda item: item[0], reverse=True)
        for _, raw_list in applicable_past_entries:
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                slot = item.get("slot")
                if slot is None:
                    continue
                slot_int = int(slot)
                ability_obj = item.get("ability")

                if ability_obj is None:
                    # Slot was not present in this historical generation
                    abilities_by_slot.pop(slot_int, None)
                else:
                    ability_name = (
                        ability_obj.get("name") if isinstance(ability_obj, dict) else None
                    )
                    if not ability_name:
                        raise PokeApiNormalizationError(
                            f"Malformed ability object in past_abilities slot {slot_int}"
                        )
                    abilities_by_slot[slot_int] = {
                        "slot": slot_int,
                        "ability_id": str(ability_name).strip().lower(),
                        "is_hidden": bool(item.get("is_hidden", False)),
                    }

        # Generation III mechanic constraint: Hidden Abilities were introduced in Gen V
        if target_generation == 3:
            abilities_by_slot = {
                s: a for s, a in abilities_by_slot.items() if not a["is_hidden"]
            }

        sorted_abilities = [
            NormalizedAbilityAssignment(
                slot=a["slot"],
                ability_id=a["ability_id"],
                is_hidden=a["is_hidden"],
            )
            for a in sorted(abilities_by_slot.values(), key=lambda x: x["slot"])
        ]

        return tuple(sorted_abilities)

    @classmethod
    def _resolve_historical_base_stats(
        cls,
        pokemon_payload: dict[str, Any],
        target_generation: int,
    ) -> NormalizedBaseStats:
        """Resolve the active six battle base stats for the target generation.

        Starts with the current 6 stats. Inspects past_stats entries where N >= G, applying
        field-level overrides in reverse chronological order. Ignores obsolete Gen I 'special'
        stat for Gen II+.
        """
        raw_stats_list = pokemon_payload.get("stats", [])
        if not isinstance(raw_stats_list, list):
            raise PokeApiNormalizationError("'stats' in pokemon_payload must be a list.")

        resolved_stats: dict[str, int] = {}
        for item in raw_stats_list:
            if not isinstance(item, dict):
                continue
            stat_name = item.get("stat", {}).get("name")
            base_stat = item.get("base_stat")
            if stat_name and base_stat is not None:
                resolved_stats[str(stat_name).strip().lower()] = int(base_stat)

        missing_stats = REQUIRED_BATTLE_STATS - set(resolved_stats.keys())
        if missing_stats:
            raise PokeApiNormalizationError(
                f"Missing required battle stats in pokemon_payload: {sorted(missing_stats)}"
            )

        past_stats = pokemon_payload.get("past_stats", [])
        if not isinstance(past_stats, list):
            raise PokeApiNormalizationError("'past_stats' must be a list.")

        applicable_past_entries: list[tuple[int, list[dict[str, Any]]]] = []
        for entry in past_stats:
            if not isinstance(entry, dict):
                continue
            gen_number = cls.parse_generation_number(entry.get("generation"))
            if gen_number is None:
                raise PokeApiNormalizationError(
                    f"Malformed generation reference in past_stats: {entry.get('generation')}"
                )
            if gen_number >= target_generation:
                raw_stat_list = entry.get("stats", [])
                if not isinstance(raw_stat_list, list):
                    raise PokeApiNormalizationError("Stats in past_stats must be a list.")
                applicable_past_entries.append((gen_number, raw_stat_list))

        # Sort descending (apply newer past overrides before older past overrides)
        applicable_past_entries.sort(key=lambda item: item[0], reverse=True)
        for _, raw_list in applicable_past_entries:
            for item in raw_list:
                if not isinstance(item, dict):
                    continue
                s_name = item.get("stat", {}).get("name")
                b_stat = item.get("base_stat")
                if not s_name or b_stat is None:
                    continue

                clean_name = str(s_name).strip().lower()
                # For Gen II+, ignore obsolete Generation I unified 'special' stat
                if clean_name == "special" and target_generation >= 2:
                    continue

                if clean_name in resolved_stats:
                    resolved_stats[clean_name] = int(b_stat)

        return NormalizedBaseStats(
            hp=resolved_stats["hp"],
            atk=resolved_stats["attack"],
            def_=resolved_stats["defense"],
            spa=resolved_stats["special-attack"],
            spd=resolved_stats["special-defense"],
            spe=resolved_stats["speed"],
        )
