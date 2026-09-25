import pytest

from app.core.errors import GameNotFoundError
from app.engines.rules_engine import GameRulesEngine, rules_engine
from app.models.domain import (
    Generation,
    PhysicalSpecialModel,
    PokemonType,
    TypeChartVersion,
)


class TestGameRulesEngine:
    """Test suite for the pure domain Game Rules Engine."""

    def test_firered_resolves_to_generation_3(self) -> None:
        """Verify that FireRed resolves to Generation III."""
        profile = rules_engine.resolve("firered")
        assert profile.generation == Generation.GEN_3
        assert profile.generation == 3

    def test_pokemon_x_resolves_to_generation_6(self) -> None:
        """Verify that Pokémon X resolves to Generation VI."""
        profile = rules_engine.resolve("pokemon_x")
        assert profile.generation == Generation.GEN_6
        assert profile.generation == 6

    def test_firered_has_17_supported_types(self) -> None:
        """Verify that FireRed has exactly 17 supported types."""
        profile = rules_engine.resolve("firered")
        assert len(profile.supported_types) == 17
        assert len(set(profile.supported_types)) == 17

    def test_pokemon_x_has_18_supported_types(self) -> None:
        """Verify that Pokémon X has exactly 18 supported types."""
        profile = rules_engine.resolve("pokemon_x")
        assert len(profile.supported_types) == 18
        assert len(set(profile.supported_types)) == 18

    def test_fairy_does_not_exist_in_firered(self) -> None:
        """Verify that the Fairy type does not exist in the FireRed rule profile."""
        profile = rules_engine.resolve("firered")
        assert PokemonType.FAIRY not in profile.supported_types
        assert profile.is_type_supported(PokemonType.FAIRY) is False
        assert profile.is_type_supported("fairy") is False
        assert profile.mechanic_flags.has_fairy_type is False

    def test_fairy_exists_in_pokemon_x(self) -> None:
        """Verify that the Fairy type exists in the Pokémon X rule profile."""
        profile = rules_engine.resolve("pokemon_x")
        assert PokemonType.FAIRY in profile.supported_types
        assert profile.is_type_supported(PokemonType.FAIRY) is True
        assert profile.is_type_supported("fairy") is True
        assert profile.mechanic_flags.has_fairy_type is True

    def test_different_type_chart_versions_resolved(self) -> None:
        """Verify that FireRed and Pokémon X resolve distinct type-chart versions."""
        firered_profile = rules_engine.resolve("firered")
        x_profile = rules_engine.resolve("pokemon_x")

        assert firered_profile.type_chart_version != x_profile.type_chart_version
        assert firered_profile.type_chart_version == TypeChartVersion.GEN_2_TO_5
        assert x_profile.type_chart_version == TypeChartVersion.GEN_6_PLUS

    def test_unsupported_game_ids_raise_domain_error(self) -> None:
        """Verify that unsupported game IDs fail closed with GameNotFoundError."""
        with pytest.raises(GameNotFoundError) as exc_info:
            rules_engine.resolve("pokemon_emerald")
        assert "pokemon_emerald" in str(exc_info.value)
        assert exc_info.value.status_code == 404

        with pytest.raises(GameNotFoundError):
            rules_engine.resolve("unknown_game_123")

        with pytest.raises(GameNotFoundError):
            rules_engine.resolve("")

    def test_mechanic_flags_divergence(self) -> None:
        """Verify mechanic flags divergence between Gen III and Gen VI."""
        firered = rules_engine.resolve("firered")
        pokemon_x = rules_engine.resolve("pokemon_x")

        # Steel defensive profile
        assert firered.mechanic_flags.steel_resists_dark_ghost is True
        assert pokemon_x.mechanic_flags.steel_resists_dark_ghost is False

        # Physical / Special split
        assert firered.physical_special_model == PhysicalSpecialModel.BY_TYPE
        assert firered.mechanic_flags.physical_special_split is False

        assert pokemon_x.physical_special_model == PhysicalSpecialModel.BY_MOVE
        assert pokemon_x.mechanic_flags.physical_special_split is True

    def test_leafgreen_and_pokemon_y_support(self) -> None:
        """Verify paired versions resolve with matching generational mechanics."""
        leafgreen = rules_engine.resolve("leafgreen")
        pokemon_y = rules_engine.resolve("pokemon_y")

        assert leafgreen.generation == Generation.GEN_3
        assert leafgreen.type_chart_version == TypeChartVersion.GEN_2_TO_5

        assert pokemon_y.generation == Generation.GEN_6
        assert pokemon_y.type_chart_version == TypeChartVersion.GEN_6_PLUS

    def test_aliases_and_case_insensitivity(self) -> None:
        """Verify resolution handles common aliases and whitespace/casing cleanly."""
        assert rules_engine.resolve("  FireRed  ").game_id == "firered"
        assert rules_engine.resolve("POKEMON_X").game_id == "pokemon_x"
        assert rules_engine.resolve("x").game_id == "pokemon_x"
        assert rules_engine.resolve("y").game_id == "pokemon_y"
        assert rules_engine.resolve("pokemon-firered").game_id == "firered"

    def test_fresh_instance_isolation(self) -> None:
        """Verify that GameRulesEngine can be cleanly instantiated in isolation."""
        engine = GameRulesEngine()
        assert engine.is_game_supported("firered") is True
        assert engine.is_game_supported("unsupported_title") is False
        assert "firered" in engine.get_supported_game_ids()
        assert "pokemon_x" in engine.get_supported_game_ids()
