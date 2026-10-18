"""Test suite for Milestone 4B: Defensive Team Analysis Engine.

Validates pure type-only defensive team analysis, exact multiplier calculation,
classification, shared weakness aggregation, cross-game type chart resolution,
and structural consistency.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.core.errors import (
    DuplicateTeamMemberError,
    GameNotFoundError,
    InvalidTeamSizeError,
    InvalidTypeMatchupError,
    TeamValidationError,
    UnsupportedTypeError,
)
from app.engines.rules_engine import rules_engine
from app.engines.team_analysis_engine import team_analysis_engine
from app.models.domain import PokemonType, TypeChartVersion
from app.models.team import Team, ValidatedTeam, ValidatedTeamMember
from app.models.team_analysis import (
    DefensiveClassification,
    MemberDefensiveMatchup,
    SharedWeakness,
    SharedWeaknessMember,
    TeamDefensiveAnalysis,
    TypeDefenseAnalysis,
    classify_multiplier,
)
from app.services.ingestion_service import IngestionService
from app.services.pokemon_service import PokemonAbilityInfo, PokemonBaseStatsInfo
from app.services.team_service import TeamValidationService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def analysis_db(db_session: Session) -> Session:
    """Provide a database seeded with canonical games and Clefairy/Pidgeot."""
    IngestionService.seed_game_contexts(db_session)

    clef_data = _load_fixture("pokeapi_clefairy")
    pidg_data = _load_fixture("pokeapi_pidgeot")

    norm_clef = PokeApiNormalizer.normalize_pokemon(
        clef_data["pokemon"], clef_data["species"], "firered"
    )
    norm_pidg = PokeApiNormalizer.normalize_pokemon(
        pidg_data["pokemon"], pidg_data["species"], "firered"
    )
    IngestionService.ingest_pokemon(db_session, norm_clef)
    IngestionService.ingest_pokemon(db_session, norm_pidg)
    return db_session


# ==============================================================================
# Helpers for Constructing Test Members
# ==============================================================================


def _make_member(
    slot: int,
    pokemon_id: str,
    types: tuple[PokemonType, ...],
    name: str = "TestMon",
    abilities: tuple[PokemonAbilityInfo, ...] = (),
    is_anchor: bool = False,
) -> ValidatedTeamMember:
    """Helper creating a ValidatedTeamMember for testing."""
    return ValidatedTeamMember(
        slot=slot,
        pokemon_id=pokemon_id,
        dex_number=1,
        name=name,
        species_name=pokemon_id,
        form_name=None,
        types=types,
        abilities=abilities,
        base_stats=PokemonBaseStatsInfo(hp=50, atk=50, def_=50, spa=50, spd=50, spe=50),
        is_anchor=is_anchor,
    )


# ==============================================================================
# 1. Purity, Immutability & Contract Tests
# ==============================================================================


class TestDefensiveAnalysisPurityAndImmutability:
    """Verifies that all analysis models are strictly immutable and pure."""

    def test_classify_multiplier(self) -> None:
        """Verify multiplier to DefensiveClassification mapping."""
        assert classify_multiplier(0.0) == DefensiveClassification.IMMUNE
        assert classify_multiplier(0.25) == DefensiveClassification.RESISTANT
        assert classify_multiplier(0.5) == DefensiveClassification.RESISTANT
        assert classify_multiplier(1.0) == DefensiveClassification.NEUTRAL
        assert classify_multiplier(2.0) == DefensiveClassification.WEAK
        assert classify_multiplier(4.0) == DefensiveClassification.WEAK

        with pytest.raises(InvalidTypeMatchupError):
            classify_multiplier(-1.0)

    def test_analysis_models_immutability(self) -> None:
        """Verify frozen dataclasses raise FrozenInstanceError on mutation."""
        matchup = MemberDefensiveMatchup(
            pokemon_id="bulbasaur",
            slot=1,
            multiplier=2.0,
            classification=DefensiveClassification.WEAK,
        )
        with pytest.raises(FrozenInstanceError):
            matchup.multiplier = 1.0  # type: ignore[misc]

        weak_member = SharedWeaknessMember(pokemon_id="bulbasaur", slot=1, multiplier=2.0)
        with pytest.raises(FrozenInstanceError):
            weak_member.multiplier = 1.0  # type: ignore[misc]

        shared_weakness = SharedWeakness(
            attacking_type=PokemonType.ICE,
            count=1,
            members=(weak_member,),
        )
        with pytest.raises(FrozenInstanceError):
            shared_weakness.count = 2  # type: ignore[misc]

        type_analysis = TypeDefenseAnalysis(
            attacking_type=PokemonType.ICE,
            member_matchups=(matchup,),
            weak_count=1,
            neutral_count=0,
            resistant_count=0,
            immune_count=0,
            is_shared_weakness=False,
        )
        with pytest.raises(FrozenInstanceError):
            type_analysis.weak_count = 2  # type: ignore[misc]

        team_analysis = TeamDefensiveAnalysis(
            game_id="firered",
            type_chart_version=TypeChartVersion.GEN_2_TO_5,
            type_matchups=(type_analysis,),
            shared_weaknesses=(),
        )
        with pytest.raises(FrozenInstanceError):
            team_analysis.analysis_mode = "custom"  # type: ignore[misc]

    def test_purity_input_team_unmutated(self) -> None:
        """Decision 4: Verify analyze_defenses does not mutate input ValidatedTeam."""
        member = _make_member(
            slot=1,
            pokemon_id="bulbasaur",
            types=(PokemonType.GRASS, PokemonType.POISON),
            abilities=(
                PokemonAbilityInfo(ability_id="overgrow", name="Overgrow", is_hidden=False),
            ),
        )
        team = ValidatedTeam(game_id="firered", members=(member,))

        # Snapshot attributes
        original_game_id = team.game_id
        original_members_count = len(team.members)
        original_member_types = team.members[0].types
        original_member_abilities = team.members[0].abilities
        original_member_stats = team.members[0].base_stats

        # Execute analysis
        analysis = team_analysis_engine.analyze_defenses(team)

        # Assert input team remains strictly unchanged
        assert team.game_id == original_game_id
        assert len(team.members) == original_members_count
        assert team.members[0].types == original_member_types
        assert team.members[0].abilities == original_member_abilities
        assert team.members[0].base_stats == original_member_stats
        assert analysis.analysis_mode == "type_only"


# ==============================================================================
# 2. Defensive Multipliers & Classification Tests
# ==============================================================================


class TestDefensiveMultipliersAndClassification:
    """Verifies single and dual type defense calculations and classifications."""

    def test_single_type_defender(self) -> None:
        """Verify single-type defender (Fire) in FireRed."""
        charmander = _make_member(slot=1, pokemon_id="charmander", types=(PokemonType.FIRE,))
        team = ValidatedTeam(game_id="firered", members=(charmander,))
        analysis = team_analysis_engine.analyze_defenses(team)

        # Weaknesses: Water (2.0), Ground (2.0), Rock (2.0)
        water_row = analysis.get_analysis_for_type(PokemonType.WATER)
        assert water_row.weak_count == 1
        assert water_row.member_matchups[0].multiplier == 2.0
        assert water_row.member_matchups[0].classification == DefensiveClassification.WEAK

        # Resistances: Fire (0.5), Grass (0.5), Ice (0.5), Bug (0.5), Steel (0.5)
        grass_row = analysis.get_analysis_for_type(PokemonType.GRASS)
        assert grass_row.resistant_count == 1
        assert grass_row.member_matchups[0].multiplier == 0.5
        assert grass_row.member_matchups[0].classification == DefensiveClassification.RESISTANT

        # Neutral: Electric (1.0), Normal (1.0)
        normal_row = analysis.get_analysis_for_type(PokemonType.NORMAL)
        assert normal_row.neutral_count == 1
        assert normal_row.member_matchups[0].multiplier == 1.0
        assert normal_row.member_matchups[0].classification == DefensiveClassification.NEUTRAL

    def test_dual_type_defender_immunities_and_quad_effects(self) -> None:
        """Verify dual-type defender with immunities (0x) and quad effects (0.25x, 4x)."""
        # Bulbasaur: Grass / Poison
        bulbasaur = _make_member(
            slot=1, pokemon_id="bulbasaur", types=(PokemonType.GRASS, PokemonType.POISON)
        )
        team = ValidatedTeam(game_id="firered", members=(bulbasaur,))
        analysis = team_analysis_engine.analyze_defenses(team)

        # Grass against Grass/Poison is 0.5 * 0.5 = 0.25x (Quarter resistance)
        grass_row = analysis.get_analysis_for_type(PokemonType.GRASS)
        assert grass_row.resistant_count == 1
        assert grass_row.member_matchups[0].multiplier == 0.25
        assert grass_row.member_matchups[0].classification == DefensiveClassification.RESISTANT

        # Pidgeot: Normal / Flying (Immune to Ground 0.0x and Ghost 0.0x)
        pidgeot = _make_member(
            slot=1, pokemon_id="pidgeot", types=(PokemonType.NORMAL, PokemonType.FLYING)
        )
        team2 = ValidatedTeam(game_id="firered", members=(pidgeot,))
        analysis2 = team_analysis_engine.analyze_defenses(team2)

        ground_row = analysis2.get_analysis_for_type(PokemonType.GROUND)
        assert ground_row.immune_count == 1
        assert ground_row.member_matchups[0].multiplier == 0.0
        assert ground_row.member_matchups[0].classification == DefensiveClassification.IMMUNE

        ghost_row = analysis2.get_analysis_for_type(PokemonType.GHOST)
        assert ghost_row.immune_count == 1
        assert ghost_row.member_matchups[0].multiplier == 0.0

    def test_quad_weakness_calculation(self) -> None:
        """Verify 4.0x quad weakness on dual-type defender (e.g. Grass/Bug vs Fire)."""
        parasect = _make_member(
            slot=1, pokemon_id="parasect", types=(PokemonType.BUG, PokemonType.GRASS)
        )
        team = ValidatedTeam(game_id="firered", members=(parasect,))
        analysis = team_analysis_engine.analyze_defenses(team)

        fire_row = analysis.get_analysis_for_type(PokemonType.FIRE)
        assert fire_row.weak_count == 1
        assert fire_row.member_matchups[0].multiplier == 4.0
        assert fire_row.member_matchups[0].classification == DefensiveClassification.WEAK


# ==============================================================================
# 3. Shared Weakness Reporting Tests
# ==============================================================================


class TestSharedWeaknessReporting:
    """Verifies shared weakness detection and reporting for teams."""

    def test_one_member_team_has_zero_shared_weaknesses(self) -> None:
        """One-member teams must have empty shared weaknesses even with individual weaknesses."""
        bulbasaur = _make_member(
            slot=1, pokemon_id="bulbasaur", types=(PokemonType.GRASS, PokemonType.POISON)
        )
        team = ValidatedTeam(game_id="firered", members=(bulbasaur,))
        analysis = team_analysis_engine.analyze_defenses(team)

        assert analysis.shared_weaknesses == ()
        assert analysis.shared_weakness_types == ()

        # Individual weakness to Fire exists
        fire_row = analysis.get_analysis_for_type(PokemonType.FIRE)
        assert fire_row.weak_count == 1
        assert fire_row.is_shared_weakness is False

    def test_two_member_team_shared_weakness_detected(self) -> None:
        """Two members sharing a weakness (Ice) are flagged as a shared weakness."""
        # Bulbasaur (Grass/Poison) weak to Ice (2.0)
        bulbasaur = _make_member(
            slot=1, pokemon_id="bulbasaur", types=(PokemonType.GRASS, PokemonType.POISON)
        )
        # Pidgeot (Normal/Flying) weak to Ice (2.0)
        pidgeot = _make_member(
            slot=2, pokemon_id="pidgeot", types=(PokemonType.NORMAL, PokemonType.FLYING)
        )
        team = ValidatedTeam(game_id="firered", members=(bulbasaur, pidgeot))
        analysis = team_analysis_engine.analyze_defenses(team)

        # Ice is a shared weakness
        ice_row = analysis.get_analysis_for_type(PokemonType.ICE)
        assert ice_row.weak_count == 2
        assert ice_row.is_shared_weakness is True
        assert ice_row.weak_pokemon_ids == ("bulbasaur", "pidgeot")

        # Check shared_weaknesses summary
        assert PokemonType.ICE in analysis.shared_weakness_types
        shared_ice = [w for w in analysis.shared_weaknesses if w.attacking_type == PokemonType.ICE]
        assert len(shared_ice) == 1
        assert shared_ice[0].count == 2
        assert len(shared_ice[0].members) == 2
        assert shared_ice[0].members[0].pokemon_id == "bulbasaur"
        assert shared_ice[0].members[0].slot == 1
        assert shared_ice[0].members[0].multiplier == 2.0
        assert shared_ice[0].members[1].pokemon_id == "pidgeot"
        assert shared_ice[0].members[1].slot == 2
        assert shared_ice[0].members[1].multiplier == 2.0

        # Electric is weak for Pidgeot (2.0) but resistant for Bulbasaur (0.5) -> not shared
        elec_row = analysis.get_analysis_for_type(PokemonType.ELECTRIC)
        assert elec_row.weak_count == 1
        assert elec_row.resistant_count == 1
        assert elec_row.is_shared_weakness is False

    def test_team_with_no_shared_weaknesses(self) -> None:
        """Verify team with complementary typings has empty shared weaknesses."""
        # Snorlax (Normal: weak only to Fighting)
        snorlax = _make_member(slot=1, pokemon_id="snorlax", types=(PokemonType.NORMAL,))
        # Gengar (Ghost/Poison: weak to Ground, Psychic, Ghost, Dark; immune to Fighting)
        gengar = _make_member(
            slot=2, pokemon_id="gengar", types=(PokemonType.GHOST, PokemonType.POISON)
        )
        # Snorlax is immune to Ghost; neutral to Ground, Psychic, Dark.
        # Neither shares Fighting weakness (Gengar is immune).
        team = ValidatedTeam(game_id="firered", members=(snorlax, gengar))
        analysis = team_analysis_engine.analyze_defenses(team)

        # Check each weakness of Snorlax (Fighting)
        fighting_row = analysis.get_analysis_for_type(PokemonType.FIGHTING)
        assert fighting_row.weak_count == 1
        assert fighting_row.immune_count == 1
        assert fighting_row.is_shared_weakness is False

        # None of Gengar's weaknesses are shared by Snorlax
        for t in (PokemonType.GROUND, PokemonType.PSYCHIC, PokemonType.GHOST, PokemonType.DARK):
            assert analysis.get_analysis_for_type(t).weak_count == 1

        assert analysis.shared_weaknesses == ()
        assert analysis.shared_weakness_types == ()

    def test_full_six_member_team_counts_sum(self) -> None:
        """Verify full 6-member team counts sum to 6 for all attacking types."""
        m1 = _make_member(slot=1, pokemon_id="m1", types=(PokemonType.FIRE,))
        m2 = _make_member(slot=2, pokemon_id="m2", types=(PokemonType.WATER,))
        m3 = _make_member(slot=3, pokemon_id="m3", types=(PokemonType.GRASS,))
        m4 = _make_member(slot=4, pokemon_id="m4", types=(PokemonType.ELECTRIC,))
        m5 = _make_member(slot=5, pokemon_id="m5", types=(PokemonType.GROUND,))
        m6 = _make_member(slot=6, pokemon_id="m6", types=(PokemonType.FLYING,))

        team = ValidatedTeam(game_id="firered", members=(m1, m2, m3, m4, m5, m6))
        analysis = team_analysis_engine.analyze_defenses(team)

        assert len(analysis.type_matchups) == 17
        for type_row in analysis.type_matchups:
            total_counted = (
                type_row.weak_count
                + type_row.neutral_count
                + type_row.resistant_count
                + type_row.immune_count
            )
            assert total_counted == 6
            assert len(type_row.member_matchups) == 6


# ==============================================================================
# 4. Ordering & Helper Methods Tests
# ==============================================================================


class TestOrderingAndHelperMethods:
    """Verifies deterministic member and attacking-type ordering and helper accessors."""

    def test_member_and_attacking_type_ordering(self) -> None:
        """Verify attacking types follow rule profile and members follow team slots."""
        m1 = _make_member(slot=1, pokemon_id="bulbasaur", types=(PokemonType.GRASS,))
        m2 = _make_member(slot=2, pokemon_id="charmander", types=(PokemonType.FIRE,))
        team = ValidatedTeam(game_id="firered", members=(m1, m2))
        analysis = team_analysis_engine.analyze_defenses(team)

        rule_profile = rules_engine.resolve("firered")
        # Attacking types exactly match rule profile supported types
        assert tuple(t.attacking_type for t in analysis.type_matchups) == (
            rule_profile.supported_types
        )

        # In every row, members follow slot 1, slot 2 order
        for type_row in analysis.type_matchups:
            assert [m.slot for m in type_row.member_matchups] == [1, 2]
            assert [m.pokemon_id for m in type_row.member_matchups] == ["bulbasaur", "charmander"]

    def test_get_member_matchups(self) -> None:
        """Verify get_member_matchups returns complete ordered list for a member."""
        m1 = _make_member(slot=1, pokemon_id="charmander", types=(PokemonType.FIRE,))
        m2 = _make_member(slot=2, pokemon_id="squirtle", types=(PokemonType.WATER,))
        team = ValidatedTeam(game_id="firered", members=(m1, m2))
        analysis = team_analysis_engine.analyze_defenses(team)

        charmander_matchups = analysis.get_member_matchups("charmander")
        assert len(charmander_matchups) == 17
        assert all(m.pokemon_id == "charmander" for m in charmander_matchups)
        assert charmander_matchups[0].slot == 1

        with pytest.raises(KeyError):
            analysis.get_member_matchups("nonexistent")

    def test_unresisted_types_and_resistor_properties(self) -> None:
        """Verify unresisted_types identifies types with 0 resistors and 0 immunities."""
        # Team of purely Normal Pokémon: resists nothing, immune to Ghost
        snorlax = _make_member(slot=1, pokemon_id="snorlax", types=(PokemonType.NORMAL,))
        team = ValidatedTeam(game_id="firered", members=(snorlax,))
        analysis = team_analysis_engine.analyze_defenses(team)

        # Ghost has immunity (total_resisted_count = 1)
        ghost_row = analysis.get_analysis_for_type("ghost")
        assert ghost_row.has_resistor_or_immunity is True
        assert PokemonType.GHOST not in analysis.unresisted_types

        # Fire has 0 resistors and 0 immunities for pure Normal
        fire_row = analysis.get_analysis_for_type("fire")
        assert fire_row.has_resistor_or_immunity is False
        assert PokemonType.FIRE in analysis.unresisted_types


# ==============================================================================
# 5. Ability Independence (Type-Only Baseline)
# ==============================================================================


class TestAbilityIndependence:
    """Decision 1: Verify baseline analysis is strictly type-only and never infers abilities."""

    def test_gengar_ground_matchup_is_weak_in_baseline(self) -> None:
        """Gengar has Levitate in catalog, but baseline must evaluate Ground as 2.0x weak."""
        gengar = _make_member(
            slot=1,
            pokemon_id="gengar",
            types=(PokemonType.GHOST, PokemonType.POISON),
            abilities=(
                PokemonAbilityInfo(ability_id="levitate", name="Levitate", is_hidden=False),
            ),
        )
        team = ValidatedTeam(game_id="firered", members=(gengar,))
        analysis = team_analysis_engine.analyze_defenses(team)

        ground_row = analysis.get_analysis_for_type(PokemonType.GROUND)
        assert ground_row.weak_count == 1
        assert ground_row.immune_count == 0
        assert ground_row.member_matchups[0].multiplier == 2.0
        assert ground_row.member_matchups[0].classification == DefensiveClassification.WEAK


# ==============================================================================
# 6. Cross-Game Correctness & Isolation Tests
# ==============================================================================


class TestCrossGameDefensiveAnalysis:
    """Verifies generational type chart differences and game context isolation."""

    def test_firered_has_17_types_and_no_fairy(self) -> None:
        """FireRed analysis contains exactly 17 types and Fairy is absent."""
        snorlax = _make_member(slot=1, pokemon_id="snorlax", types=(PokemonType.NORMAL,))
        team = ValidatedTeam(game_id="firered", members=(snorlax,))
        analysis = team_analysis_engine.analyze_defenses(team)

        assert len(analysis.type_matchups) == 17
        assert PokemonType.FAIRY not in [t.attacking_type for t in analysis.type_matchups]

        with pytest.raises(KeyError):
            analysis.get_analysis_for_type(PokemonType.FAIRY)

    def test_pokemon_x_has_18_types_including_fairy(self) -> None:
        """Pokémon X analysis contains 18 types including Fairy."""
        snorlax = _make_member(slot=1, pokemon_id="snorlax", types=(PokemonType.NORMAL,))
        team = ValidatedTeam(game_id="pokemon-x", members=(snorlax,))
        analysis = team_analysis_engine.analyze_defenses(team)

        assert len(analysis.type_matchups) == 18
        assert PokemonType.FAIRY in [t.attacking_type for t in analysis.type_matchups]
        fairy_row = analysis.get_analysis_for_type(PokemonType.FAIRY)
        assert fairy_row.attacking_type == PokemonType.FAIRY
        assert fairy_row.member_matchups[0].multiplier == 1.0  # Normal is neutral to Fairy

    def test_clefairy_cross_game_typing_defenses(self) -> None:
        """Clefairy is Normal in FireRed vs Fairy in Pokémon X; defensive profiles diverge."""
        clefairy_fr = _make_member(slot=1, pokemon_id="clefairy", types=(PokemonType.NORMAL,))
        clefairy_x = _make_member(slot=1, pokemon_id="clefairy", types=(PokemonType.FAIRY,))

        team_fr = ValidatedTeam(game_id="firered", members=(clefairy_fr,))
        team_x = ValidatedTeam(game_id="pokemon-x", members=(clefairy_x,))

        analysis_fr = team_analysis_engine.analyze_defenses(team_fr)
        analysis_x = team_analysis_engine.analyze_defenses(team_x)

        # Fighting: FireRed (Normal) is Weak (2.0x); Pokémon X (Fairy) is Resistant (0.5x)
        assert analysis_fr.get_analysis_for_type("fighting").member_matchups[0].multiplier == 2.0
        assert (
            analysis_fr.get_analysis_for_type("fighting").member_matchups[0].classification
            == DefensiveClassification.WEAK
        )
        assert analysis_x.get_analysis_for_type("fighting").member_matchups[0].multiplier == 0.5
        assert (
            analysis_x.get_analysis_for_type("fighting").member_matchups[0].classification
            == DefensiveClassification.RESISTANT
        )

        # Ghost: FireRed is Immune (0.0x); Pokémon X is Neutral (1.0x)
        assert analysis_fr.get_analysis_for_type("ghost").member_matchups[0].multiplier == 0.0
        assert (
            analysis_fr.get_analysis_for_type("ghost").member_matchups[0].classification
            == DefensiveClassification.IMMUNE
        )
        assert analysis_x.get_analysis_for_type("ghost").member_matchups[0].multiplier == 1.0
        assert (
            analysis_x.get_analysis_for_type("ghost").member_matchups[0].classification
            == DefensiveClassification.NEUTRAL
        )

        # Dragon: FireRed is Neutral (1.0x); Pokémon X is Immune (0.0x)
        assert analysis_fr.get_analysis_for_type("dragon").member_matchups[0].multiplier == 1.0
        assert analysis_x.get_analysis_for_type("dragon").member_matchups[0].multiplier == 0.0

        # Steel: FireRed is Neutral (1.0x); Pokémon X is Weak (2.0x)
        assert analysis_fr.get_analysis_for_type("steel").member_matchups[0].multiplier == 1.0
        assert analysis_x.get_analysis_for_type("steel").member_matchups[0].multiplier == 2.0

        # Poison: FireRed is Neutral (1.0x); Pokémon X is Weak (2.0x)
        assert analysis_fr.get_analysis_for_type("poison").member_matchups[0].multiplier == 1.0
        assert analysis_x.get_analysis_for_type("poison").member_matchups[0].multiplier == 2.0

    def test_steel_ghost_and_dark_resistance_divergence(self) -> None:
        """Steel resists Ghost and Dark in Gen 3 (0.5x), but is neutral in Gen 6 (1.0x)."""
        steel_fr = _make_member(slot=1, pokemon_id="steelix", types=(PokemonType.STEEL,))
        steel_x = _make_member(slot=1, pokemon_id="steelix", types=(PokemonType.STEEL,))

        team_fr = ValidatedTeam(game_id="firered", members=(steel_fr,))
        team_x = ValidatedTeam(game_id="pokemon-x", members=(steel_x,))

        analysis_fr = team_analysis_engine.analyze_defenses(team_fr)
        analysis_x = team_analysis_engine.analyze_defenses(team_x)

        # Gen 3 (FireRed): Steel resists Ghost and Dark (0.5x)
        assert analysis_fr.get_analysis_for_type("ghost").member_matchups[0].multiplier == 0.5
        assert analysis_fr.get_analysis_for_type("dark").member_matchups[0].multiplier == 0.5

        # Gen 6 (Pokémon X): Steel is neutral to Ghost and Dark (1.0x)
        assert analysis_x.get_analysis_for_type("ghost").member_matchups[0].multiplier == 1.0
        assert analysis_x.get_analysis_for_type("dark").member_matchups[0].multiplier == 1.0


# ==============================================================================
# 7. Structural Consistency & Error Handling (Decision 3)
# ==============================================================================


class TestStructuralConsistencyAndErrors:
    """Decision 3: Enforce game-rule consistency and reject invalid team structures."""

    def test_reject_non_validated_team(self) -> None:
        """Verify non-ValidatedTeam object raises TeamValidationError."""
        with pytest.raises(TeamValidationError):
            team_analysis_engine.analyze_defenses("not-a-team")  # type: ignore[arg-type]

    def test_reject_empty_team(self) -> None:
        """Verify empty members raises InvalidTeamSizeError."""
        # Bypass ValidatedTeam post_init to test engine defense-in-depth
        team = ValidatedTeam.__new__(ValidatedTeam)
        object.__setattr__(team, "game_id", "firered")
        object.__setattr__(team, "members", ())
        with pytest.raises(InvalidTeamSizeError):
            team_analysis_engine.analyze_defenses(team)

    def test_reject_team_exceeding_six_members(self) -> None:
        """Verify > 6 members raises InvalidTeamSizeError."""
        members = tuple(
            _make_member(slot=i, pokemon_id=f"p{i}", types=(PokemonType.NORMAL,))
            for i in range(1, 8)
        )
        team = ValidatedTeam.__new__(ValidatedTeam)
        object.__setattr__(team, "game_id", "firered")
        object.__setattr__(team, "members", members)
        with pytest.raises(InvalidTeamSizeError):
            team_analysis_engine.analyze_defenses(team)

    def test_reject_invalid_or_out_of_sequence_slots(self) -> None:
        """Verify non-sequential or duplicate slots raise TeamValidationError."""
        m1 = _make_member(slot=1, pokemon_id="bulbasaur", types=(PokemonType.GRASS,))
        m2 = _make_member(slot=3, pokemon_id="charmander", types=(PokemonType.FIRE,))
        team = ValidatedTeam(game_id="firered", members=(m1, m2))

        with pytest.raises(TeamValidationError) as exc_info:
            team_analysis_engine.analyze_defenses(team)
        assert "slots are invalid" in str(exc_info.value).lower()

    def test_reject_duplicate_pokemon_ids(self) -> None:
        """Verify duplicate pokemon_ids raise DuplicateTeamMemberError."""
        m1 = _make_member(slot=1, pokemon_id="bulbasaur", types=(PokemonType.GRASS,))
        m2 = _make_member(slot=2, pokemon_id="Bulbasaur", types=(PokemonType.GRASS,))
        team = ValidatedTeam(game_id="firered", members=(m1, m2))

        with pytest.raises(DuplicateTeamMemberError):
            team_analysis_engine.analyze_defenses(team)

    def test_reject_unsupported_member_type_for_game(self) -> None:
        """Verify member with Fairy type is rejected in FireRed."""
        clefairy_fairy = _make_member(slot=1, pokemon_id="clefairy", types=(PokemonType.FAIRY,))
        team = ValidatedTeam(game_id="firered", members=(clefairy_fairy,))

        with pytest.raises(UnsupportedTypeError) as exc_info:
            team_analysis_engine.analyze_defenses(team)
        assert "fairy" in str(exc_info.value).lower()
        assert "not supported in game 'firered'" in str(exc_info.value).lower()

    def test_reject_unknown_game_id(self) -> None:
        """Verify unknown game ID raises GameNotFoundError."""
        m = _make_member(slot=1, pokemon_id="bulbasaur", types=(PokemonType.GRASS,))
        team = ValidatedTeam(game_id="emerald", members=(m,))

        with pytest.raises(GameNotFoundError):
            team_analysis_engine.analyze_defenses(team)


# ==============================================================================
# 8. End-to-End Integration with TeamValidationService
# ==============================================================================


class TestEndToEndTeamAnalysisIntegration:
    """Verifies end-to-end integration: Database -> TeamValidationService -> TeamAnalysisEngine."""

    def test_e2e_validated_team_defensive_analysis(self, analysis_db: Session) -> None:
        """Verify team validated against database fixtures can be analyzed cleanly."""
        # Team in FireRed: Clefairy (Normal) + Pidgeot (Normal/Flying)
        raw_team = Team(game_id="firered", pokemon_ids=("clefairy", "pidgeot"))
        validated = TeamValidationService.validate_team(analysis_db, raw_team)

        analysis = team_analysis_engine.analyze_defenses(validated)

        assert analysis.game_id == "firered"
        assert analysis.analysis_mode == "type_only"
        assert len(analysis.type_matchups) == 17

        # Fighting is weak for Clefairy (2.0) and neutral for Pidgeot (1.0) -> not shared
        fight_row = analysis.get_analysis_for_type("fighting")
        assert fight_row.weak_count == 1
        assert fight_row.neutral_count == 1
        assert fight_row.is_shared_weakness is False

        # Ghost is immune for both Clefairy (0.0) and Pidgeot (0.0)
        ghost_row = analysis.get_analysis_for_type("ghost")
        assert ghost_row.immune_count == 2
        assert ghost_row.total_resisted_count == 2
        assert ghost_row.has_resistor_or_immunity is True
