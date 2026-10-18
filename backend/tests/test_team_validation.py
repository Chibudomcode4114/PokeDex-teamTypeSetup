"""Unit and integration tests for Team Domain Models and TeamValidationService (Milestone 4A).

Executes strictly against the internal normalized relational database using offline fixtures.
Verifies immutable team models, 1-6 member validation, duplicate prevention, anchor resolution,
game context isolation, ability metadata preservation, and distinct form preservation.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.adapters.pokeapi.normalizer import PokeApiNormalizer
from app.adapters.pokeapi.schemas import (
    NormalizedAbilityAssignment,
    NormalizedBaseStats,
    NormalizedPokemon,
    NormalizedTypeAssignment,
)
from app.core.errors import (
    DuplicateTeamMemberError,
    GameNotFoundError,
    InvalidAnchorError,
    InvalidTeamSizeError,
    PokemonNotFoundError,
    PokemonUnavailableInGameError,
)
from app.models.domain import PokemonType
from app.models.team import Team, ValidatedTeam, ValidatedTeamMember
from app.services.ingestion_service import IngestionService
from app.services.pokemon_service import PokemonAbilityInfo, PokemonBaseStatsInfo
from app.services.team_service import TeamValidationService

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict[str, Any]:
    """Load JSON fixture from local test fixtures."""
    path = FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def team_db(db_session: Session) -> Session:
    """Provide a database seeded with canonical game contexts and representative test Pokémon."""
    IngestionService.seed_game_contexts(db_session)

    clef_data = load_fixture("pokeapi_clefairy")
    pidg_data = load_fixture("pokeapi_pidgeot")
    geng_data = load_fixture("pokeapi_gengar")
    deox_data = load_fixture("pokeapi_deoxys_attack")

    # Ingest Clefairy into FireRed (Normal) and Pokémon X (Fairy)
    norm_clef_fr = PokeApiNormalizer.normalize_pokemon(
        clef_data["pokemon"], clef_data["species"], "firered"
    )
    norm_clef_x = PokeApiNormalizer.normalize_pokemon(
        clef_data["pokemon"], clef_data["species"], "pokemon-x"
    )
    IngestionService.ingest_pokemon(db_session, norm_clef_fr)
    IngestionService.ingest_pokemon(db_session, norm_clef_x)

    # Ingest Pidgeot into FireRed (Spe 91) and Pokémon X (Spe 101)
    norm_pidg_fr = PokeApiNormalizer.normalize_pokemon(
        pidg_data["pokemon"], pidg_data["species"], "firered"
    )
    norm_pidg_x = PokeApiNormalizer.normalize_pokemon(
        pidg_data["pokemon"], pidg_data["species"], "pokemon-x"
    )
    IngestionService.ingest_pokemon(db_session, norm_pidg_fr)
    IngestionService.ingest_pokemon(db_session, norm_pidg_x)

    # Ingest Gengar into FireRed and Pokémon X
    norm_geng_fr = PokeApiNormalizer.normalize_pokemon(
        geng_data["pokemon"], geng_data["species"], "firered"
    )
    norm_geng_x = PokeApiNormalizer.normalize_pokemon(
        geng_data["pokemon"], geng_data["species"], "pokemon-x"
    )
    IngestionService.ingest_pokemon(db_session, norm_geng_fr)
    IngestionService.ingest_pokemon(db_session, norm_geng_x)

    # Ingest Deoxys Attack into FireRed only (Dex 386, Form attack)
    norm_deox_fr = PokeApiNormalizer.normalize_pokemon(
        deox_data["pokemon"], deox_data["species"], "firered"
    )
    IngestionService.ingest_pokemon(db_session, norm_deox_fr)

    # Ingest Bulbasaur into FireRed
    norm_bulba_fr = NormalizedPokemon(
        id="bulbasaur",
        dex_number=1,
        name="Bulbasaur",
        species_name="bulbasaur",
        form_name=None,
        is_default=True,
        slug="bulbasaur",
        game_id="firered",
        types=(
            NormalizedTypeAssignment(slot=1, type_id="grass"),
            NormalizedTypeAssignment(slot=2, type_id="poison"),
        ),
        abilities=(NormalizedAbilityAssignment(slot=1, ability_id="overgrow", is_hidden=False),),
        base_stats=NormalizedBaseStats(hp=45, atk=49, def_=49, spa=65, spd=65, spe=45),
        is_available=True,
    )
    IngestionService.ingest_pokemon(db_session, norm_bulba_fr)

    # Ingest Charmander into FireRed
    norm_char_fr = NormalizedPokemon(
        id="charmander",
        dex_number=4,
        name="Charmander",
        species_name="charmander",
        form_name=None,
        is_default=True,
        slug="charmander",
        game_id="firered",
        types=(NormalizedTypeAssignment(slot=1, type_id="fire"),),
        abilities=(NormalizedAbilityAssignment(slot=1, ability_id="blaze", is_hidden=False),),
        base_stats=NormalizedBaseStats(hp=39, atk=52, def_=43, spa=60, spd=50, spe=65),
        is_available=True,
    )
    IngestionService.ingest_pokemon(db_session, norm_char_fr)

    # Ingest Unown into FireRed as UNAVAILABLE for isolation testing
    unavail_norm = NormalizedPokemon(
        id="unown",
        dex_number=201,
        name="Unown",
        species_name="unown",
        form_name=None,
        is_default=True,
        slug="unown",
        game_id="firered",
        types=(NormalizedTypeAssignment(slot=1, type_id="psychic"),),
        abilities=(NormalizedAbilityAssignment(slot=1, ability_id="levitate", is_hidden=False),),
        base_stats=NormalizedBaseStats(hp=48, atk=72, def_=48, spa=72, spd=48, spe=48),
        is_available=False,
    )
    IngestionService.ingest_pokemon(db_session, unavail_norm)

    return db_session


# ==============================================================================
# 1. Team Domain Model & Immutability Tests
# ==============================================================================


class TestTeamDomainModels:
    """Test suite verifying immutability and contract preservation of team models."""

    def test_team_construction_and_immutability(self) -> None:
        """Verify Team creates an immutable tuple copy and input list changes do not affect it."""
        roster_input = ["clefairy", "pidgeot"]
        team = Team(game_id="firered", pokemon_ids=roster_input, anchor_pokemon_id="clefairy")

        assert team.game_id == "firered"
        assert team.pokemon_ids == ("clefairy", "pidgeot")
        assert team.anchor_pokemon_id == "clefairy"

        # Modifying input list after Team construction MUST NOT mutate team.pokemon_ids
        roster_input.append("gengar")
        assert team.pokemon_ids == ("clefairy", "pidgeot")
        assert len(roster_input) == 3

        # Mutating team fields raises FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            team.game_id = "pokemon-x"  # type: ignore[misc]

        with pytest.raises(FrozenInstanceError):
            team.pokemon_ids = ("gengar",)  # type: ignore[misc]

    def test_validated_team_immutability(self) -> None:
        """Verify ValidatedTeam and ValidatedTeamMember are strictly frozen."""
        member = ValidatedTeamMember(
            slot=1,
            pokemon_id="clefairy",
            dex_number=35,
            name="Clefairy",
            species_name="clefairy",
            form_name=None,
            types=(PokemonType.NORMAL,),
            abilities=(
                PokemonAbilityInfo(ability_id="cute-charm", name="Cute Charm", is_hidden=False),
            ),
            base_stats=PokemonBaseStatsInfo(hp=70, atk=45, def_=48, spa=60, spd=65, spe=35),
            is_anchor=True,
        )
        val_team = ValidatedTeam(
            game_id="firered",
            members=(member,),
            anchor_pokemon_id="clefairy",
        )

        assert val_team.size == 1
        assert val_team.pokemon_ids == ("clefairy",)
        assert val_team.anchor_member == member

        # Mutating member raises FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            member.is_anchor = False  # type: ignore[misc]

        # Mutating team raises FrozenInstanceError
        with pytest.raises(FrozenInstanceError):
            val_team.anchor_pokemon_id = None  # type: ignore[misc]


# ==============================================================================
# 2. Team Size Validation Tests (1-6 members)
# ==============================================================================


class TestTeamSizeValidation:
    """Test suite verifying team size enforcement (1 to 6 Pokémon)."""

    def test_single_pokemon_team_valid(self, team_db: Session) -> None:
        """Verify a team with 1 Pokémon is valid."""
        team = Team(game_id="firered", pokemon_ids=("clefairy",))
        validated = TeamValidationService.validate_team(team_db, team)

        assert validated.size == 1
        assert validated.game_id == "firered"
        assert validated.members[0].pokemon_id == "clefairy"
        assert validated.members[0].slot == 1

    def test_full_six_pokemon_team_valid(self, team_db: Session) -> None:
        """Verify a team with 6 Pokémon is valid."""
        team = Team(
            game_id="firered",
            pokemon_ids=(
                "clefairy",
                "pidgeot",
                "gengar",
                "deoxys-attack",
                "bulbasaur",
                "charmander",
            ),
        )
        validated = TeamValidationService.validate_team(team_db, team)

        assert validated.size == 6
        assert [m.slot for m in validated.members] == [1, 2, 3, 4, 5, 6]
        assert validated.pokemon_ids == (
            "clefairy",
            "pidgeot",
            "gengar",
            "deoxys-attack",
            "bulbasaur",
            "charmander",
        )

    def test_empty_team_raises_error(self, team_db: Session) -> None:
        """Verify an empty team raises InvalidTeamSizeError."""
        team = Team(game_id="firered", pokemon_ids=())
        with pytest.raises(InvalidTeamSizeError) as exc_info:
            TeamValidationService.validate_team(team_db, team)
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_team_exceeding_six_raises_error(self, team_db: Session) -> None:
        """Verify a team with 7 Pokémon raises InvalidTeamSizeError."""
        team = Team(
            game_id="firered",
            pokemon_ids=(
                "clefairy",
                "pidgeot",
                "gengar",
                "deoxys-attack",
                "bulbasaur",
                "charmander",
                "unown",
            ),
        )
        with pytest.raises(InvalidTeamSizeError) as exc_info:
            TeamValidationService.validate_team(team_db, team)
        assert "cannot exceed 6" in str(exc_info.value).lower()


# ==============================================================================
# 3. Duplicate Prevention & Identifier Handling Tests
# ==============================================================================


class TestDuplicatePrevention:
    """Test suite verifying duplicate member detection and canonical identifier handling."""

    def test_exact_duplicate_rejected(self, team_db: Session) -> None:
        """Verify identical duplicate Pokémon identifiers raise DuplicateTeamMemberError."""
        team = Team(game_id="firered", pokemon_ids=("clefairy", "pidgeot", "clefairy"))
        with pytest.raises(DuplicateTeamMemberError) as exc_info:
            TeamValidationService.validate_team(team_db, team)
        assert "duplicate" in str(exc_info.value).lower()
        assert "clefairy" in str(exc_info.value).lower()

    def test_case_insensitive_duplicate_rejected(self, team_db: Session) -> None:
        """Verify case-insensitive variations raise DuplicateTeamMemberError."""
        team = Team(game_id="firered", pokemon_ids=("Clefairy", "clefairy"))
        with pytest.raises(DuplicateTeamMemberError) as exc_info:
            TeamValidationService.validate_team(team_db, team)
        assert "duplicate" in str(exc_info.value).lower()

    def test_whitespace_padded_duplicate_rejected(self, team_db: Session) -> None:
        """Verify whitespace padded duplicates are caught."""
        team = Team(game_id="firered", pokemon_ids=("pidgeot", "  pidgeot  "))
        with pytest.raises(DuplicateTeamMemberError):
            TeamValidationService.validate_team(team_db, team)

    def test_empty_string_identifier_rejected(self, team_db: Session) -> None:
        """Verify blank or empty string identifier raises PokemonNotFoundError."""
        team = Team(game_id="firered", pokemon_ids=("clefairy", "  "))
        with pytest.raises(PokemonNotFoundError):
            TeamValidationService.validate_team(team_db, team)

    def test_distinct_forms_allowed_together(self, team_db: Session) -> None:
        """Verify distinct forms of a species are preserved as distinct members."""
        # Deoxys-attack has distinct id 'deoxys-attack'
        team = Team(game_id="firered", pokemon_ids=("clefairy", "deoxys-attack"))
        validated = TeamValidationService.validate_team(team_db, team)

        assert validated.size == 2
        deox = validated.members[1]
        assert deox.pokemon_id == "deoxys-attack"
        assert deox.dex_number == 386
        assert deox.species_name == "deoxys"
        assert deox.form_name == "attack"


# ==============================================================================
# 4. Anchor Pokémon Validation Tests
# ==============================================================================


class TestAnchorValidation:
    """Test suite verifying anchor Pokémon resolution and isolation."""

    def test_valid_anchor_designated(self, team_db: Session) -> None:
        """Verify valid anchor assigns is_anchor=True only to the designated member."""
        team = Team(
            game_id="firered",
            pokemon_ids=("pidgeot", "clefairy", "gengar"),
            anchor_pokemon_id="clefairy",
        )
        validated = TeamValidationService.validate_team(team_db, team)

        assert validated.anchor_pokemon_id == "clefairy"
        assert validated.anchor_member is not None
        assert validated.anchor_member.pokemon_id == "clefairy"

        # Check member flags
        assert validated.members[0].is_anchor is False  # pidgeot
        assert validated.members[1].is_anchor is True  # clefairy
        assert validated.members[2].is_anchor is False  # gengar

    def test_case_insensitive_anchor_match(self, team_db: Session) -> None:
        """Verify anchor matching is case-insensitive."""
        team = Team(
            game_id="firered",
            pokemon_ids=("pidgeot", "clefairy"),
            anchor_pokemon_id="CLEFAIRY",
        )
        validated = TeamValidationService.validate_team(team_db, team)

        assert validated.anchor_pokemon_id == "clefairy"
        assert validated.members[1].is_anchor is True

    def test_invalid_anchor_not_in_team_rejected(self, team_db: Session) -> None:
        """Verify specifying an anchor that is not on the team raises InvalidAnchorError."""
        team = Team(
            game_id="firered",
            pokemon_ids=("pidgeot", "clefairy"),
            anchor_pokemon_id="gengar",  # Gengar is not in the team
        )
        with pytest.raises(InvalidAnchorError) as exc_info:
            TeamValidationService.validate_team(team_db, team)
        assert "not a member" in str(exc_info.value).lower()

    def test_no_anchor_specified(self, team_db: Session) -> None:
        """Verify omitting an anchor leaves all members with is_anchor=False."""
        team = Team(game_id="firered", pokemon_ids=("clefairy", "pidgeot"))
        validated = TeamValidationService.validate_team(team_db, team)

        assert validated.anchor_pokemon_id is None
        assert validated.anchor_member is None
        assert all(m.is_anchor is False for m in validated.members)


# ==============================================================================
# 5. Game Context Resolution & Isolation Tests
# ==============================================================================


class TestGameContextIsolation:
    """Test suite verifying cross-game context isolation and rule enforcement."""

    def test_unknown_game_rejected(self, team_db: Session) -> None:
        """Verify unsupported or nonexistent game raises GameNotFoundError."""
        team = Team(game_id="pokemon-emerald", pokemon_ids=("clefairy",))
        with pytest.raises(GameNotFoundError):
            TeamValidationService.validate_team(team_db, team)

    def test_game_alias_resolution(self, team_db: Session) -> None:
        """Verify game alias e.g. 'x' resolves to canonical 'pokemon-x'."""
        team = Team(game_id="x", pokemon_ids=("clefairy",))
        validated = TeamValidationService.validate_team(team_db, team)
        assert validated.game_id == "pokemon-x"

    def test_clefairy_cross_game_typing(self, team_db: Session) -> None:
        """Verify Clefairy has Normal type in FireRed and Fairy type in Pokémon X."""
        # FireRed (Gen III)
        val_fr = TeamValidationService.validate_team(
            team_db, Team(game_id="firered", pokemon_ids=("clefairy",))
        )
        assert val_fr.members[0].types == (PokemonType.NORMAL,)

        # Pokémon X (Gen VI)
        val_x = TeamValidationService.validate_team(
            team_db, Team(game_id="pokemon-x", pokemon_ids=("clefairy",))
        )
        assert val_x.members[0].types == (PokemonType.FAIRY,)

    def test_pidgeot_cross_game_stats(self, team_db: Session) -> None:
        """Verify Pidgeot Speed stat is 91 in FireRed and 101 in Pokémon X."""
        # FireRed
        val_fr = TeamValidationService.validate_team(
            team_db, Team(game_id="firered", pokemon_ids=("pidgeot",))
        )
        assert val_fr.members[0].base_stats.spe == 91

        # Pokémon X
        val_x = TeamValidationService.validate_team(
            team_db, Team(game_id="pokemon-x", pokemon_ids=("pidgeot",))
        )
        assert val_x.members[0].base_stats.spe == 101

    def test_complete_ability_metadata_preserved(self, team_db: Session) -> None:
        """Verify available abilities preserve ID, display name, and is_hidden metadata."""
        val = TeamValidationService.validate_team(
            team_db, Team(game_id="firered", pokemon_ids=("gengar",))
        )
        gengar = val.members[0]
        assert len(gengar.abilities) >= 1
        levitate = gengar.abilities[0]
        assert isinstance(levitate, PokemonAbilityInfo)
        assert levitate.ability_id == "levitate"
        assert levitate.is_hidden is False
        assert gengar.ability_ids == ("levitate",)

    def test_unknown_pokemon_rejected(self, team_db: Session) -> None:
        """Verify unknown Pokémon ID raises PokemonNotFoundError."""
        team = Team(game_id="firered", pokemon_ids=("clefairy", "agumon"))
        with pytest.raises(PokemonNotFoundError) as exc_info:
            TeamValidationService.validate_team(team_db, team)
        assert "not found" in str(exc_info.value).lower()

    def test_unavailable_pokemon_in_game_rejected(self, team_db: Session) -> None:
        """Verify Pokémon in catalog but unavailable in game raises error."""
        # Unown is ingested with is_available=False in FireRed
        team = Team(game_id="firered", pokemon_ids=("clefairy", "unown"))
        with pytest.raises(PokemonUnavailableInGameError) as exc_info:
            TeamValidationService.validate_team(team_db, team)
        assert "not available in game" in str(exc_info.value).lower()

    def test_team_order_preservation(self, team_db: Session) -> None:
        """Verify user's team order is strictly preserved and slots match."""
        # Intentionally non-alphabetical and non-dex order
        order = ("gengar", "clefairy", "pidgeot")
        val = TeamValidationService.validate_team(
            team_db, Team(game_id="firered", pokemon_ids=order)
        )

        assert val.pokemon_ids == order
        assert val.members[0].pokemon_id == "gengar"
        assert val.members[0].slot == 1
        assert val.members[1].pokemon_id == "clefairy"
        assert val.members[1].slot == 2
        assert val.members[2].pokemon_id == "pidgeot"
        assert val.members[2].slot == 3
