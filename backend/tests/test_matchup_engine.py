import pytest

from app.core.errors import InvalidTypeMatchupError, UnsupportedTypeError
from app.engines.matchup_engine import TypeMatchupEngine, matchup_engine
from app.engines.rules_engine import rules_engine
from app.models.domain import PokemonType, TypeChartVersion


class TestTypeMatchupEngineBasic:
    """Basic type interaction tests across single and dual defending types."""

    def test_water_attacks_fire(self) -> None:
        """Water -> Fire = 2.0."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.WATER, PokemonType.FIRE, TypeChartVersion.GEN_6_PLUS
        )
        assert mult == 2.0

    def test_fire_attacks_water(self) -> None:
        """Fire -> Water = 0.5."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.FIRE, PokemonType.WATER, TypeChartVersion.GEN_6_PLUS
        )
        assert mult == 0.5

    def test_normal_attacks_ghost_immunity(self) -> None:
        """Normal -> Ghost = 0.0."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.NORMAL, PokemonType.GHOST, TypeChartVersion.GEN_6_PLUS
        )
        assert mult == 0.0

    def test_electric_attacks_ground_immunity(self) -> None:
        """Electric -> Ground = 0.0."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.ELECTRIC, PokemonType.GROUND, TypeChartVersion.GEN_6_PLUS
        )
        assert mult == 0.0

    def test_rock_attacks_fire_flying(self) -> None:
        """Rock -> Fire/Flying = 4.0 (2.0 * 2.0)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.ROCK,
            (PokemonType.FIRE, PokemonType.FLYING),
            TypeChartVersion.GEN_6_PLUS,
        )
        assert mult == 4.0

    def test_grass_attacks_water_ground(self) -> None:
        """Grass -> Water/Ground = 4.0 (2.0 * 2.0)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.GRASS,
            (PokemonType.WATER, PokemonType.GROUND),
            TypeChartVersion.GEN_6_PLUS,
        )
        assert mult == 4.0

    def test_fire_attacks_water_dragon(self) -> None:
        """Fire -> Water/Dragon = 0.25 (0.5 * 0.5)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.FIRE,
            (PokemonType.WATER, PokemonType.DRAGON),
            TypeChartVersion.GEN_6_PLUS,
        )
        assert mult == 0.25

    def test_neutral_interaction(self) -> None:
        """Normal -> Water = 1.0 (neutral damage)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.NORMAL, PokemonType.WATER, TypeChartVersion.GEN_6_PLUS
        )
        assert mult == 1.0

    def test_immunity_with_weakness_remains_zero(self) -> None:
        """Electric -> Ground/Flying = 0.0 (immunity overrides 2x weakness)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.ELECTRIC,
            (PokemonType.GROUND, PokemonType.FLYING),
            TypeChartVersion.GEN_6_PLUS,
        )
        assert mult == 0.0


class TestCrossGenerationTypeMatchups:
    """Verifies that type interactions correctly diverge across generational rules."""

    def test_dark_attacks_steel_gen2_to_5(self) -> None:
        """Dark -> Steel = 0.5 in GEN_2_TO_5 (Steel resists Dark)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.DARK, PokemonType.STEEL, TypeChartVersion.GEN_2_TO_5
        )
        assert mult == 0.5

    def test_dark_attacks_steel_gen6_plus(self) -> None:
        """Dark -> Steel = 1.0 in GEN_6_PLUS (Steel lost Dark resistance)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.DARK, PokemonType.STEEL, TypeChartVersion.GEN_6_PLUS
        )
        assert mult == 1.0

    def test_ghost_attacks_steel_gen2_to_5(self) -> None:
        """Ghost -> Steel = 0.5 in GEN_2_TO_5 (Steel resists Ghost)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.GHOST, PokemonType.STEEL, TypeChartVersion.GEN_2_TO_5
        )
        assert mult == 0.5

    def test_ghost_attacks_steel_gen6_plus(self) -> None:
        """Ghost -> Steel = 1.0 in GEN_6_PLUS (Steel lost Ghost resistance)."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.GHOST, PokemonType.STEEL, TypeChartVersion.GEN_6_PLUS
        )
        assert mult == 1.0

    def test_fairy_interactions_work_in_gen6_plus(self) -> None:
        """Fairy interactions are fully functional in GEN_6_PLUS."""
        chart = TypeChartVersion.GEN_6_PLUS

        # Fairy attacking
        assert matchup_engine.calculate_matchup(
            PokemonType.FAIRY, PokemonType.DRAGON, chart
        ) == 2.0
        assert matchup_engine.calculate_matchup(
            PokemonType.FAIRY, PokemonType.STEEL, chart
        ) == 0.5
        assert matchup_engine.calculate_matchup(
            PokemonType.FAIRY, PokemonType.FIRE, chart
        ) == 0.5

        # Defending against Fairy
        assert matchup_engine.calculate_matchup(
            PokemonType.DRAGON, PokemonType.FAIRY, chart
        ) == 0.0
        assert matchup_engine.calculate_matchup(
            PokemonType.POISON, PokemonType.FAIRY, chart
        ) == 2.0
        assert matchup_engine.calculate_matchup(
            PokemonType.STEEL, PokemonType.FAIRY, chart
        ) == 2.0
        assert matchup_engine.calculate_matchup(
            PokemonType.FIGHTING, PokemonType.FAIRY, chart
        ) == 0.5

    def test_fairy_is_rejected_for_gen2_to_5(self) -> None:
        """Fairy must be explicitly rejected in GEN_2_TO_5 contexts."""
        chart = TypeChartVersion.GEN_2_TO_5

        # Fairy attacking in Gen 2-5 must fail
        with pytest.raises(UnsupportedTypeError) as exc_info:
            matchup_engine.calculate_matchup(PokemonType.FAIRY, PokemonType.DRAGON, chart)
        assert "fairy" in str(exc_info.value).lower()

        # Defending with Fairy in Gen 2-5 must fail
        with pytest.raises(UnsupportedTypeError) as exc_info:
            matchup_engine.calculate_matchup(PokemonType.FIRE, PokemonType.FAIRY, chart)
        assert "fairy" in str(exc_info.value).lower()


class TestTypeMatchupEngineContextAndValidation:
    """Verifies GameRuleProfile context integration and input validation."""

    def test_calculation_with_game_rule_profiles(self) -> None:
        """Verify calculations using GameRuleProfile directly."""
        firered = rules_engine.resolve("firered")
        pokemon_x = rules_engine.resolve("pokemon_x")

        # Dark -> Steel in FireRed vs Pokémon X
        assert matchup_engine.calculate_matchup(
            PokemonType.DARK, PokemonType.STEEL, firered
        ) == 0.5
        assert matchup_engine.calculate_matchup(
            PokemonType.DARK, PokemonType.STEEL, pokemon_x
        ) == 1.0

        # Fairy in Pokémon X works, in FireRed fails
        assert matchup_engine.calculate_matchup(
            PokemonType.POISON, PokemonType.FAIRY, pokemon_x
        ) == 2.0
        with pytest.raises(UnsupportedTypeError):
            matchup_engine.calculate_matchup(
                PokemonType.POISON, PokemonType.FAIRY, firered
            )

    def test_string_inputs_and_case_insensitivity(self) -> None:
        """Verify string types and casing work cleanly."""
        assert matchup_engine.calculate_matchup("WATER", "FIRE", "gen6_plus") == 2.0
        assert matchup_engine.calculate_matchup(
            "rock", ["fire", "flying"], "gen6_plus"
        ) == 4.0

    def test_duplicate_defending_type_deduplicated(self) -> None:
        """Passing pure type twice (e.g. Water/Water) does not square the multiplier."""
        mult = matchup_engine.calculate_matchup(
            PokemonType.ELECTRIC,
            (PokemonType.WATER, PokemonType.WATER),
            TypeChartVersion.GEN_6_PLUS,
        )
        assert mult == 2.0

    def test_empty_defending_types_raises_error(self) -> None:
        """Empty defending types must raise InvalidTypeMatchupError."""
        with pytest.raises(InvalidTypeMatchupError):
            matchup_engine.calculate_matchup(
                PokemonType.WATER, (), TypeChartVersion.GEN_6_PLUS
            )

    def test_more_than_two_defending_types_raises_error(self) -> None:
        """More than two defending types must raise InvalidTypeMatchupError."""
        with pytest.raises(InvalidTypeMatchupError):
            matchup_engine.calculate_matchup(
                PokemonType.ROCK,
                (PokemonType.FIRE, PokemonType.FLYING, PokemonType.ICE),
                TypeChartVersion.GEN_6_PLUS,
            )

    def test_invalid_type_string_raises_error(self) -> None:
        """Invalid type names raise UnsupportedTypeError."""
        with pytest.raises(UnsupportedTypeError):
            matchup_engine.calculate_matchup("cosmic", "fire", TypeChartVersion.GEN_6_PLUS)

    def test_invalid_chart_version_raises_error(self) -> None:
        """Invalid chart version string raises UnsupportedTypeError."""
        with pytest.raises(UnsupportedTypeError):
            matchup_engine.calculate_matchup("water", "fire", "gen99")

    def test_matchup_result_structure(self) -> None:
        """Verify get_matchup_result returns structured TypeMatchupResult."""
        result = matchup_engine.get_matchup_result(
            PokemonType.ROCK,
            (PokemonType.FIRE, PokemonType.FLYING),
            TypeChartVersion.GEN_6_PLUS,
        )
        assert result.attacking_type == PokemonType.ROCK
        assert result.defending_types == (PokemonType.FIRE, PokemonType.FLYING)
        assert result.multiplier == 4.0
        assert result.chart_version == TypeChartVersion.GEN_6_PLUS

    def test_engine_isolation(self) -> None:
        """Verify TypeMatchupEngine can be instantiated in total isolation."""
        engine = TypeMatchupEngine()
        assert engine.calculate_single_matchup(
            PokemonType.WATER, PokemonType.FIRE, TypeChartVersion.GEN_6_PLUS
        ) == 2.0
