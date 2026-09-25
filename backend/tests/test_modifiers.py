from app.engines.matchup_engine import matchup_engine
from app.engines.modifiers import (
    DefensiveModifierPipeline,
    modifier_pipeline,
)
from app.engines.rules_engine import rules_engine
from app.models.domain import (
    GameRuleProfile,
    Generation,
    MechanicFlags,
    PhysicalSpecialModel,
    PokemonType,
    TypeChartVersion,
    TypeMatchupResult,
)


class TestAbilityModifiers:
    """Test suite for individual ability modifiers and pipeline execution."""

    def test_levitate_ground_weakness_negated(self) -> None:
        """Levitate turns a 2.0x Ground weakness into 0.0x immunity."""
        profile = rules_engine.resolve("firered")
        # Poison/Ghost defending (e.g. Gengar in Gen 3 with Levitate)
        base = matchup_engine.get_matchup_result(
            PokemonType.GROUND, (PokemonType.POISON, PokemonType.GHOST), profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="Levitate")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 0.0
        assert "Levitate" in modified.applied_modifiers
        assert modified.was_modified is True

    def test_levitate_ground_neutral_negated(self) -> None:
        """Levitate turns a 1.0x Ground neutral interaction into 0.0x immunity."""
        profile = rules_engine.resolve("pokemon_x")
        base = matchup_engine.get_matchup_result(
            PokemonType.GROUND, PokemonType.NORMAL, profile
        )
        assert base.multiplier == 1.0

        modified = modifier_pipeline.apply(base, profile, ability="levitate")
        assert modified.base_multiplier == 1.0
        assert modified.final_multiplier == 0.0
        assert "Levitate" in modified.applied_modifiers

    def test_levitate_unrelated_attack_unchanged(self) -> None:
        """Non-Ground attacks are unaffected by Levitate."""
        profile = rules_engine.resolve("firered")
        base = matchup_engine.get_matchup_result(
            PokemonType.PSYCHIC, (PokemonType.POISON, PokemonType.GHOST), profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="Levitate")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 2.0
        assert len(modified.applied_modifiers) == 0
        assert modified.was_modified is False

    def test_flash_fire_negates_fire(self) -> None:
        """Flash Fire turns Fire attacks into 0.0x immunity."""
        profile = rules_engine.resolve("firered")
        # Grass defender normally weak to Fire (2.0x)
        base = matchup_engine.get_matchup_result(
            PokemonType.FIRE, PokemonType.GRASS, profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="Flash Fire")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 0.0
        assert "Flash Fire" in modified.applied_modifiers

    def test_flash_fire_unrelated_attack_unchanged(self) -> None:
        """Non-Fire attacks are unaffected by Flash Fire."""
        profile = rules_engine.resolve("firered")
        base = matchup_engine.get_matchup_result(
            PokemonType.WATER, PokemonType.FIRE, profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="flash-fire")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 2.0
        assert len(modified.applied_modifiers) == 0

    def test_water_absorb_negates_water(self) -> None:
        """Water Absorb turns Water attacks into 0.0x immunity."""
        profile = rules_engine.resolve("pokemon_x")
        base = matchup_engine.get_matchup_result(
            PokemonType.WATER, PokemonType.GROUND, profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="Water Absorb")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 0.0
        assert "Water Absorb" in modified.applied_modifiers

    def test_volt_absorb_negates_electric(self) -> None:
        """Volt Absorb turns Electric attacks into 0.0x immunity."""
        profile = rules_engine.resolve("pokemon_x")
        base = matchup_engine.get_matchup_result(
            PokemonType.ELECTRIC, PokemonType.WATER, profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="volt-absorb")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 0.0
        assert "Volt Absorb" in modified.applied_modifiers

    def test_thick_fat_fire_weakness_halved(self) -> None:
        """Thick Fat halves 2.0x Fire weakness to 1.0x."""
        profile = rules_engine.resolve("firered")
        base = matchup_engine.get_matchup_result(
            PokemonType.FIRE, PokemonType.GRASS, profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="Thick Fat")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 1.0
        assert "Thick Fat" in modified.applied_modifiers

    def test_thick_fat_fire_neutral_halved(self) -> None:
        """Thick Fat halves 1.0x Fire neutral to 0.5x."""
        profile = rules_engine.resolve("firered")
        base = matchup_engine.get_matchup_result(
            PokemonType.FIRE, PokemonType.NORMAL, profile
        )
        assert base.multiplier == 1.0

        modified = modifier_pipeline.apply(base, profile, ability="thick_fat")
        assert modified.base_multiplier == 1.0
        assert modified.final_multiplier == 0.5

    def test_thick_fat_ice_quad_weakness_halved(self) -> None:
        """Thick Fat halves 4.0x Ice weakness to 2.0x."""
        profile = rules_engine.resolve("pokemon_x")
        # Grass/Flying defender (e.g. Tropius) weak to Ice (4.0x)
        base = matchup_engine.get_matchup_result(
            PokemonType.ICE, (PokemonType.GRASS, PokemonType.FLYING), profile
        )
        assert base.multiplier == 4.0

        modified = modifier_pipeline.apply(base, profile, ability="Thick Fat")
        assert modified.base_multiplier == 4.0
        assert modified.final_multiplier == 2.0

    def test_thick_fat_unrelated_attack_unchanged(self) -> None:
        """Thick Fat has no effect on Fighting or other non-Fire/Ice attacks."""
        profile = rules_engine.resolve("firered")
        base = matchup_engine.get_matchup_result(
            PokemonType.FIGHTING, PokemonType.NORMAL, profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="Thick Fat")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 2.0
        assert len(modified.applied_modifiers) == 0


class TestPipelineEdgeCasesAndPurity:
    """Test suite for pipeline edge cases, immutability, and game context."""

    def test_no_ability_leaves_multiplier_unchanged(self) -> None:
        """Supplying None or empty string leaves base multiplier unaltered."""
        profile = rules_engine.resolve("firered")
        base = matchup_engine.get_matchup_result(
            PokemonType.WATER, PokemonType.FIRE, profile
        )
        assert base.multiplier == 2.0

        modified_none = modifier_pipeline.apply(base, profile, ability=None)
        assert modified_none.base_multiplier == 2.0
        assert modified_none.final_multiplier == 2.0
        assert len(modified_none.applied_modifiers) == 0

        modified_empty = modifier_pipeline.apply(base, profile, ability="")
        assert modified_empty.final_multiplier == 2.0

    def test_unimplemented_ability_leaves_multiplier_unchanged(self) -> None:
        """Abilities with no defensive modifier (e.g. Intimidate) leave result unchanged."""
        profile = rules_engine.resolve("pokemon_x")
        base = matchup_engine.get_matchup_result(
            PokemonType.GROUND, PokemonType.FIRE, profile
        )
        assert base.multiplier == 2.0

        modified = modifier_pipeline.apply(base, profile, ability="Intimidate")
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 2.0
        assert len(modified.applied_modifiers) == 0

    def test_original_matchup_result_is_not_mutated(self) -> None:
        """Verify input TypeMatchupResult retains original values."""
        profile = rules_engine.resolve("firered")
        base = TypeMatchupResult(
            attacking_type=PokemonType.GROUND,
            defending_types=(PokemonType.POISON,),
            multiplier=2.0,
            chart_version=TypeChartVersion.GEN_2_TO_5,
        )

        modified = modifier_pipeline.apply(base, profile, ability="Levitate")
        # Base result must remain untouched
        assert base.multiplier == 2.0
        assert modified.base_multiplier == 2.0
        assert modified.final_multiplier == 0.0

    def test_modifiers_work_in_both_game_rule_profiles(self) -> None:
        """Verify modifiers evaluate properly in both FireRed and Pokémon X contexts."""
        firered = rules_engine.resolve("firered")
        pokemon_x = rules_engine.resolve("pokemon_x")

        base_fr = matchup_engine.get_matchup_result(
            PokemonType.GROUND, PokemonType.POISON, firered
        )
        base_x = matchup_engine.get_matchup_result(
            PokemonType.GROUND, PokemonType.POISON, pokemon_x
        )

        mod_fr = modifier_pipeline.apply(base_fr, firered, ability="Levitate")
        mod_x = modifier_pipeline.apply(base_x, pokemon_x, ability="Levitate")

        assert mod_fr.final_multiplier == 0.0
        assert mod_x.final_multiplier == 0.0

    def test_game_without_abilities_ignores_modifiers(self) -> None:
        """If a hypothetical game profile lacks abilities, modifiers do not trigger."""
        no_ability_profile = GameRuleProfile(
            game_id="classic_gen1",
            game_title="Classic Gen 1",
            generation=Generation.GEN_1,
            type_chart_version=TypeChartVersion.GEN_1,
            physical_special_model=PhysicalSpecialModel.BY_TYPE,
            supported_types=rules_engine.resolve("firered").supported_types,
            mechanic_flags=MechanicFlags(
                has_fairy_type=False,
                steel_resists_dark_ghost=False,
                physical_special_split=False,
                has_abilities=False,  # Abilities disabled
            ),
        )

        base = TypeMatchupResult(
            attacking_type=PokemonType.GROUND,
            defending_types=(PokemonType.FIRE,),
            multiplier=2.0,
            chart_version=TypeChartVersion.GEN_1,
        )

        modified = modifier_pipeline.apply(
            base, no_ability_profile, ability="Levitate"
        )
        assert modified.final_multiplier == 2.0
        assert len(modified.applied_modifiers) == 0

    def test_custom_pipeline_instance_isolation(self) -> None:
        """Verify pipeline can be configured with an arbitrary subset of modifiers."""
        custom_pipeline = DefensiveModifierPipeline(modifiers=[])
        profile = rules_engine.resolve("firered")
        base = matchup_engine.get_matchup_result(
            PokemonType.GROUND, PokemonType.FIRE, profile
        )

        # Empty pipeline applies nothing
        modified = custom_pipeline.apply(base, profile, ability="Levitate")
        assert modified.final_multiplier == 2.0
