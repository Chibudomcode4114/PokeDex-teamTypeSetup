"""Unit tests for PokeApiNormalizer.

Verifies deterministic transformation of raw PokeAPI JSON into game-specific data models.
Tests execute entirely offline using local JSON fixtures with zero network/database calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.adapters.pokeapi.exceptions import PokeApiNormalizationError
from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.adapters.pokeapi.schemas import get_target_game_context

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(fixture_name: str) -> dict[str, Any]:
    """Load a JSON fixture from the local fixtures directory."""
    path = FIXTURES_DIR / f"{fixture_name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestPokeApiNormalizer:
    """Test suite verifying pure normalization of raw PokeAPI payloads."""

    def test_identity_and_form_handling(self) -> None:
        """Verify separation of internal ID, National Dex number, slugs, and forms."""
        # 1. Default form (Clefairy)
        clef_data = load_fixture("pokeapi_clefairy")
        norm_clef = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="firered",
        )
        assert norm_clef.id == "clefairy"
        assert norm_clef.dex_number == 35
        assert norm_clef.slug == "clefairy"
        assert norm_clef.species_name == "clefairy"
        assert norm_clef.form_name is None
        assert norm_clef.is_default is True
        assert norm_clef.name == "Clefairy"

        # 2. Alternate form (Deoxys Attack)
        deox_data = load_fixture("pokeapi_deoxys_attack")
        norm_deox = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=deox_data["pokemon"],
            species_payload=deox_data["species"],
            target_game="firered",
        )
        # Form ID 10001 must NOT become the National Dex number (must be 386)
        assert norm_deox.dex_number == 386
        assert norm_deox.id == "deoxys-attack"
        assert norm_deox.slug == "deoxys-attack"
        assert norm_deox.species_name == "deoxys"
        assert norm_deox.form_name == "attack"
        assert norm_deox.is_default is False
        assert "Attack" in norm_deox.name

    def test_historical_typing_clefairy(self) -> None:
        """Verify Clefairy is Normal in Gen III (FireRed/LeafGreen) and Fairy in Gen VI (X/Y)."""
        clef_data = load_fixture("pokeapi_clefairy")

        # FireRed (Gen III) -> Normal (slot 1)
        clef_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="firered",
        )
        assert len(clef_fr.types) == 1
        assert clef_fr.types[0].slot == 1
        assert clef_fr.types[0].type_id == "normal"

        # LeafGreen (Gen III) -> Normal (slot 1)
        clef_lg = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="leafgreen",
        )
        assert len(clef_lg.types) == 1
        assert clef_lg.types[0].slot == 1
        assert clef_lg.types[0].type_id == "normal"

        # Pokémon X (Gen VI) -> Fairy (slot 1)
        clef_x = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="pokemon-x",
        )
        assert len(clef_x.types) == 1
        assert clef_x.types[0].slot == 1
        assert clef_x.types[0].type_id == "fairy"

        # Pokémon Y (Gen VI) -> Fairy (slot 1)
        clef_y = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="pokemon-y",
        )
        assert len(clef_y.types) == 1
        assert clef_y.types[0].slot == 1
        assert clef_y.types[0].type_id == "fairy"

    def test_dual_typing_slots_preserved(self) -> None:
        """Verify multi-type slots are strictly ordered."""
        pidg_data = load_fixture("pokeapi_pidgeot")
        norm_pidg = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=pidg_data["pokemon"],
            species_payload=pidg_data["species"],
            target_game="firered",
        )
        assert len(norm_pidg.types) == 2
        assert norm_pidg.types[0].slot == 1
        assert norm_pidg.types[0].type_id == "normal"
        assert norm_pidg.types[1].slot == 2
        assert norm_pidg.types[1].type_id == "flying"

    def test_historical_abilities_gengar(self) -> None:
        """Verify Gengar resolves to Levitate in both FireRed and Pokémon X."""
        geng_data = load_fixture("pokeapi_gengar")

        # FireRed (Gen III) -> Levitate
        geng_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=geng_data["pokemon"],
            species_payload=geng_data["species"],
            target_game="firered",
        )
        assert len(geng_fr.abilities) == 1
        assert geng_fr.abilities[0].slot == 1
        assert geng_fr.abilities[0].ability_id == "levitate"
        assert geng_fr.abilities[0].is_hidden is False

        # LeafGreen (Gen III) -> Levitate
        geng_lg = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=geng_data["pokemon"],
            species_payload=geng_data["species"],
            target_game="leafgreen",
        )
        assert len(geng_lg.abilities) == 1
        assert geng_lg.abilities[0].ability_id == "levitate"

        # Pokémon X (Gen VI) -> Levitate
        geng_x = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=geng_data["pokemon"],
            species_payload=geng_data["species"],
            target_game="pokemon-x",
        )
        assert len(geng_x.abilities) == 1
        assert geng_x.abilities[0].slot == 1
        assert geng_x.abilities[0].ability_id == "levitate"

        # Pokémon Y (Gen VI) -> Levitate
        geng_y = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=geng_data["pokemon"],
            species_payload=geng_data["species"],
            target_game="pokemon-y",
        )
        assert len(geng_y.abilities) == 1
        assert geng_y.abilities[0].ability_id == "levitate"

    def test_historical_null_ability_and_hidden_ability_removal_gen3(self) -> None:
        """Verify null past_abilities remove slots and hidden abilities are excluded in Gen III."""
        clef_data = load_fixture("pokeapi_clefairy")

        # In FireRed (Gen III):
        # slot 2 is null in past_abilities (Magic Guard didn't exist)
        # slot 3 is null in past_abilities (Friend Guard didn't exist)
        # Gen III also excludes hidden abilities
        # Result: only slot 1 (Cute Charm)
        clef_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="firered",
        )
        assert len(clef_fr.abilities) == 1
        assert clef_fr.abilities[0].slot == 1
        assert clef_fr.abilities[0].ability_id == "cute-charm"
        assert clef_fr.abilities[0].is_hidden is False

        # In Pokémon X (Gen VI):
        # All 3 abilities valid: Cute Charm (1), Magic Guard (2), Friend Guard (3, hidden)
        clef_x = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="pokemon-x",
        )
        assert len(clef_x.abilities) == 3
        abilities_by_slot = {a.slot: a for a in clef_x.abilities}
        assert abilities_by_slot[1].ability_id == "cute-charm"
        assert abilities_by_slot[1].is_hidden is False
        assert abilities_by_slot[2].ability_id == "magic-guard"
        assert abilities_by_slot[2].is_hidden is False
        assert abilities_by_slot[3].ability_id == "friend-guard"
        assert abilities_by_slot[3].is_hidden is True

    def test_historical_base_stats_pidgeot(self) -> None:
        """Verify Pidgeot Speed is 91 in FireRed (Gen III) and 101 in Pokémon X (Gen VI)."""
        pidg_data = load_fixture("pokeapi_pidgeot")

        # FireRed (Gen III) -> Speed 91
        pidg_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=pidg_data["pokemon"],
            species_payload=pidg_data["species"],
            target_game="firered",
        )
        assert pidg_fr.base_stats.hp == 83
        assert pidg_fr.base_stats.atk == 80
        assert pidg_fr.base_stats.def_ == 75
        assert pidg_fr.base_stats.spa == 70
        assert pidg_fr.base_stats.spd == 70
        assert pidg_fr.base_stats.spe == 91

        # Pokémon X (Gen VI) -> Speed 101 (+10 buff active)
        pidg_x = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=pidg_data["pokemon"],
            species_payload=pidg_data["species"],
            target_game="pokemon-x",
        )
        assert pidg_x.base_stats.hp == 83
        assert pidg_x.base_stats.atk == 80
        assert pidg_x.base_stats.def_ == 75
        assert pidg_x.base_stats.spa == 70
        assert pidg_x.base_stats.spd == 70
        assert pidg_x.base_stats.spe == 101

    def test_game_availability_resolution(self) -> None:
        """Verify presence in game_indices determines availability."""
        clef_data = load_fixture("pokeapi_clefairy")

        # Available in FireRed
        clef_fr = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=clef_data["pokemon"],
            species_payload=clef_data["species"],
            target_game="firered",
        )
        assert clef_fr.is_available is True

        # Absent from an unlisted game version
        unlisted_context = get_target_game_context("firered")
        custom_pokemon = dict(clef_data["pokemon"])
        custom_pokemon["game_indices"] = [{"game_index": 35, "version": {"name": "ruby"}}]

        clef_unavail = PokeApiNormalizer.normalize_pokemon(
            pokemon_payload=custom_pokemon,
            species_payload=clef_data["species"],
            target_game=unlisted_context,
        )
        assert clef_unavail.is_available is False

    def test_validation_errors(self) -> None:
        """Verify normalization fails explicitly on missing or malformed data."""
        clef_data = load_fixture("pokeapi_clefairy")

        # 1. Unsupported game
        with pytest.raises(PokeApiNormalizationError, match="Unsupported target game"):
            PokeApiNormalizer.normalize_pokemon(
                pokemon_payload=clef_data["pokemon"],
                species_payload=clef_data["species"],
                target_game="unsupported-game",
            )

        # 2. Missing required stats
        bad_pokemon = dict(clef_data["pokemon"])
        bad_pokemon["stats"] = [{"stat": {"name": "hp"}, "base_stat": 70}]
        with pytest.raises(PokeApiNormalizationError, match="Missing required battle stats"):
            PokeApiNormalizer.normalize_pokemon(
                pokemon_payload=bad_pokemon,
                species_payload=clef_data["species"],
                target_game="firered",
            )

        # 3. Missing name
        bad_species = dict(clef_data["species"])
        del bad_species["name"]
        with pytest.raises(PokeApiNormalizationError, match="missing required 'name' field"):
            PokeApiNormalizer.normalize_pokemon(
                pokemon_payload=clef_data["pokemon"],
                species_payload=bad_species,
                target_game="firered",
            )

        # 4. Malformed past_types generation
        malformed_past_types = dict(clef_data["pokemon"])
        malformed_past_types["past_types"] = [
            {"generation": "not-a-valid-gen", "types": []}
        ]
        with pytest.raises(PokeApiNormalizationError, match="Malformed generation reference"):
            PokeApiNormalizer.normalize_pokemon(
                pokemon_payload=malformed_past_types,
                species_payload=clef_data["species"],
                target_game="firered",
            )
