"""Analysis domain models for defensive team effectiveness (Milestone 4B).

These models are immutable and strictly decoupled from database persistence and HTTP routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from app.core.errors import InvalidTypeMatchupError
from app.models.domain import PokemonType, TypeChartVersion


class DefensiveClassification(StrEnum):
    """Classification of defensive effectiveness based on damage multiplier."""

    IMMUNE = "immune"  # multiplier == 0.0
    RESISTANT = "resistant"  # 0.0 < multiplier < 1.0 (e.g. 0.25, 0.5)
    NEUTRAL = "neutral"  # multiplier == 1.0
    WEAK = "weak"  # multiplier > 1.0 (e.g. 2.0, 4.0)


def classify_multiplier(multiplier: float) -> DefensiveClassification:
    """Classify a defensive damage multiplier into an effectiveness category.

    Args:
        multiplier: Defensive damage multiplier.

    Returns:
        DefensiveClassification category.

    Raises:
        InvalidTypeMatchupError: If multiplier is negative.
    """
    if multiplier == 0.0:
        return DefensiveClassification.IMMUNE
    if 0.0 < multiplier < 1.0:
        return DefensiveClassification.RESISTANT
    if multiplier == 1.0:
        return DefensiveClassification.NEUTRAL
    if multiplier > 1.0:
        return DefensiveClassification.WEAK
    raise InvalidTypeMatchupError(f"Invalid defensive multiplier: {multiplier}")


@dataclass(frozen=True)
class MemberDefensiveMatchup:
    """Defensive multiplier and classification for a single team member against an attacking type.

    Attributes:
        pokemon_id: Canonical Pokémon identifier.
        slot: 1-indexed team roster slot (1 to 6).
        multiplier: Defensive damage multiplier (0.0, 0.25, 0.5, 1.0, 2.0, 4.0).
        classification: Defensive effectiveness classification.
    """

    pokemon_id: str
    slot: int
    multiplier: float
    classification: DefensiveClassification


@dataclass(frozen=True)
class SharedWeaknessMember:
    """Represents a member contributing to a team's shared weakness.

    Attributes:
        pokemon_id: Canonical Pokémon identifier.
        slot: 1-indexed team roster slot (1 to 6).
        multiplier: Defensive damage multiplier (>= 2.0).
    """

    pokemon_id: str
    slot: int
    multiplier: float


@dataclass(frozen=True)
class SharedWeakness:
    """A shared defensive vulnerability affecting two or more team members.

    Attributes:
        attacking_type: The elemental attacking type causing the vulnerability.
        count: Count of affected members (must be >= 2).
        members: Detailed list of affected members and their multipliers.
    """

    attacking_type: PokemonType
    count: int
    members: tuple[SharedWeaknessMember, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))

    @property
    def member_ids(self) -> tuple[str, ...]:
        """Return tuple of canonical Pokémon IDs affected by this weakness."""
        return tuple(m.pokemon_id for m in self.members)


@dataclass(frozen=True)
class TypeDefenseAnalysis:
    """Defensive analysis for an entire team against a single attacking type.

    Attributes:
        attacking_type: The incoming attacking type.
        member_matchups: Ordered tuple of matchups for each team member (slots 1 to N).
        weak_count: Number of members weak to this type (multiplier > 1.0).
        neutral_count: Number of members neutral to this type (multiplier == 1.0).
        resistant_count: Number of members resistant to this type (0.0 < multiplier < 1.0).
        immune_count: Number of members immune to this type (multiplier == 0.0).
        is_shared_weakness: True if 2 or more members are weak to this type.
    """

    attacking_type: PokemonType
    member_matchups: tuple[MemberDefensiveMatchup, ...]
    weak_count: int
    neutral_count: int
    resistant_count: int
    immune_count: int
    is_shared_weakness: bool

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_matchups", tuple(self.member_matchups))

    @property
    def total_resisted_count(self) -> int:
        """Count of members providing resistance or immunity."""
        return self.resistant_count + self.immune_count

    @property
    def has_resistor_or_immunity(self) -> bool:
        """Whether at least one member resists or is immune to this type."""
        return self.total_resisted_count > 0

    @property
    def weak_pokemon_ids(self) -> tuple[str, ...]:
        """Tuple of Pokémon IDs weak to this attacking type."""
        return tuple(
            m.pokemon_id
            for m in self.member_matchups
            if m.classification == DefensiveClassification.WEAK
        )

    @property
    def resistant_pokemon_ids(self) -> tuple[str, ...]:
        """Tuple of Pokémon IDs resistant to this attacking type."""
        return tuple(
            m.pokemon_id
            for m in self.member_matchups
            if m.classification == DefensiveClassification.RESISTANT
        )

    @property
    def immune_pokemon_ids(self) -> tuple[str, ...]:
        """Tuple of Pokémon IDs immune to this attacking type."""
        return tuple(
            m.pokemon_id
            for m in self.member_matchups
            if m.classification == DefensiveClassification.IMMUNE
        )


@dataclass(frozen=True)
class TeamDefensiveAnalysis:
    """Complete defensive analysis for a team within an authoritative game context.

    Attributes:
        game_id: Canonical game identifier.
        analysis_mode: Analysis mode ('type_only' in baseline M4B).
        type_chart_version: Generational type chart version used for evaluation.
        type_matchups: Ordered analysis for every attacking type supported by the game.
        shared_weaknesses: Shared vulnerabilities affecting two or more members.
    """

    game_id: str
    type_chart_version: TypeChartVersion
    type_matchups: tuple[TypeDefenseAnalysis, ...]
    shared_weaknesses: tuple[SharedWeakness, ...]
    analysis_mode: str = "type_only"

    def __post_init__(self) -> None:
        object.__setattr__(self, "type_matchups", tuple(self.type_matchups))
        object.__setattr__(self, "shared_weaknesses", tuple(self.shared_weaknesses))

    @property
    def shared_weakness_types(self) -> tuple[PokemonType, ...]:
        """Tuple of attacking types that are shared weaknesses for the team."""
        return tuple(w.attacking_type for w in self.shared_weaknesses)

    @property
    def unresisted_types(self) -> tuple[PokemonType, ...]:
        """Tuple of attacking types with zero resistors and zero immunities on the team."""
        return tuple(t.attacking_type for t in self.type_matchups if not t.has_resistor_or_immunity)

    def get_analysis_for_type(self, attacking_type: PokemonType | str) -> TypeDefenseAnalysis:
        """Retrieve the defensive analysis row for a specific attacking type.

        Args:
            attacking_type: PokemonType enum or string type name.

        Returns:
            The matching TypeDefenseAnalysis.

        Raises:
            KeyError: If the type is not found in this game's analysis.
        """
        norm_type = (
            attacking_type
            if isinstance(attacking_type, PokemonType)
            else PokemonType(attacking_type.strip().lower())
        )
        for t in self.type_matchups:
            if t.attacking_type == norm_type:
                return t
        raise KeyError(f"Attacking type '{norm_type.value}' not present in this team analysis.")

    def get_member_matchups(self, pokemon_id: str) -> tuple[MemberDefensiveMatchup, ...]:
        """Retrieve all attacking-type matchups for a specific team member.

        Args:
            pokemon_id: Canonical Pokémon identifier.

        Returns:
            Tuple of MemberDefensiveMatchup for every attacking type in order.

        Raises:
            KeyError: If the pokemon_id is not part of this team.
        """
        norm_id = pokemon_id.strip().lower()
        results: list[MemberDefensiveMatchup] = []
        found = False
        for type_analysis in self.type_matchups:
            for member_matchup in type_analysis.member_matchups:
                if member_matchup.pokemon_id == norm_id:
                    results.append(member_matchup)
                    found = True
                    break
        if not found:
            raise KeyError(f"Pokemon '{pokemon_id}' is not a member of this team.")
        return tuple(results)
