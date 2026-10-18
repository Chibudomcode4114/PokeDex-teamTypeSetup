"""Team domain models representing unvalidated inputs and validated team structures (Milestone 4A).

These models are immutable and strictly decoupled from database persistence and HTTP routing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.models.domain import PokemonType

if TYPE_CHECKING:
    from app.services.pokemon_service import PokemonAbilityInfo, PokemonBaseStatsInfo


@dataclass(frozen=True)
class Team:
    """User-provided unvalidated team request structure.

    Attributes:
        game_id: Target game context identifier.
        pokemon_ids: Ordered sequence of Pokémon identifiers (1 to 6).
        anchor_pokemon_id: Optional Pokémon identifier designating an anchor.
    """

    game_id: str
    pokemon_ids: tuple[str, ...]
    anchor_pokemon_id: str | None = None

    def __post_init__(self) -> None:
        # Create an immutable defensive copy of the input roster sequence
        object.__setattr__(self, "pokemon_ids", tuple(self.pokemon_ids))


@dataclass(frozen=True)
class ValidatedTeamMember:
    """Validated Pokémon team member resolved within an explicit game context.

    Note on abilities:
        The `abilities` attribute represents the catalog of available abilities for this
        Pokémon in the selected game. It does NOT assume any or all listed abilities are
        active on the player's Pokémon. Active ability selection and modifier evaluation
        are handled in subsequent analysis milestones (M4B/M4C).

    Attributes:
        slot: 1-indexed roster position (1 to 6).
        pokemon_id: Canonical Pokémon identifier.
        dex_number: National Pokédex number.
        name: Display name.
        species_name: Base species name.
        form_name: Distinct form/variety name if applicable, else None.
        types: Game-specific elemental types as PokemonType enums.
        abilities: Game-specific available abilities retaining id, name, and hidden metadata.
        base_stats: Game-specific base battle stats.
        is_anchor: Whether this member is the designated anchor.
    """

    slot: int
    pokemon_id: str
    dex_number: int
    name: str
    species_name: str
    form_name: str | None
    types: tuple[PokemonType, ...]
    abilities: tuple[PokemonAbilityInfo, ...]
    base_stats: PokemonBaseStatsInfo
    is_anchor: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "types", tuple(self.types))
        object.__setattr__(self, "abilities", tuple(self.abilities))

    @property
    def ability_ids(self) -> tuple[str, ...]:
        """Return tuple of available ability identifiers."""
        return tuple(a.ability_id for a in self.abilities)

    @property
    def type_ids(self) -> tuple[str, ...]:
        """Return tuple of elemental type string identifiers."""
        return tuple(t.value for t in self.types)


@dataclass(frozen=True)
class ValidatedTeam:
    """Fully validated Pokémon team resolved against an authoritative game context.

    Attributes:
        game_id: Canonical game context identifier.
        members: Ordered tuple of 1 to 6 validated team members.
        anchor_pokemon_id: Optional validated canonical anchor identifier.
    """

    game_id: str
    members: tuple[ValidatedTeamMember, ...]
    anchor_pokemon_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))

    @property
    def pokemon_ids(self) -> tuple[str, ...]:
        """Return ordered tuple of canonical Pokémon IDs."""
        return tuple(m.pokemon_id for m in self.members)

    @property
    def size(self) -> int:
        """Return the count of team members (1 to 6)."""
        return len(self.members)

    @property
    def anchor_member(self) -> ValidatedTeamMember | None:
        """Return the validated anchor member if one is designated, else None."""
        if self.anchor_pokemon_id is None:
            return None
        for m in self.members:
            if m.pokemon_id == self.anchor_pokemon_id:
                return m
        return None
