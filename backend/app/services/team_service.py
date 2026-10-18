"""Team Management Service: team state, editing, and game-aware validation (Milestone 4A).

Validates user-submitted teams against explicit game contexts, ensuring team size (1-6),
duplicate prevention, anchor validity, and game-specific attribute resolution.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session

from app.core.errors import (
    DuplicateTeamMemberError,
    GameNotFoundError,
    InvalidAnchorError,
    InvalidTeamSizeError,
    PokemonNotFoundError,
)
from app.models.domain import PokemonType
from app.models.team import Team, ValidatedTeam, ValidatedTeamMember
from app.services.game_service import GameCatalogService
from app.services.pokemon_service import PokemonCatalogService


class TeamValidationService:
    """Service providing game-aware validation and domain resolution for Pokémon teams."""

    MIN_TEAM_SIZE = 1
    MAX_TEAM_SIZE = 6

    @classmethod
    def validate_team(
        cls,
        session: Session,
        team: Team | None = None,
        *,
        game_id: str | None = None,
        pokemon_ids: Sequence[str] | None = None,
        anchor_pokemon_id: str | None = None,
    ) -> ValidatedTeam:
        """Validate and resolve an unvalidated team against an explicit game context.

        Args:
            session: Active SQLAlchemy database session.
            team: Optional Team domain model.
            game_id: Optional explicit game context ID (if team not provided).
            pokemon_ids: Optional sequence of Pokémon identifiers (if team not provided).
            anchor_pokemon_id: Optional anchor Pokémon identifier (if team not provided).

        Returns:
            ValidatedTeam: Immutable validated team with game-accurate members.

        Raises:
            GameNotFoundError: If game_id is missing, unknown, or unsupported.
            InvalidTeamSizeError: If team size is 0 or exceeds 6.
            DuplicateTeamMemberError: If duplicate Pokémon identifiers are present.
            InvalidAnchorError: If the anchor Pokémon is not part of the team roster.
            PokemonNotFoundError: If any Pokémon is not found in the catalog.
            PokemonUnavailableInGameError: If any Pokémon is unavailable in this game.
        """
        # 1. Resolve inputs from Team instance or individual keyword arguments
        if team is not None:
            eff_game_id = team.game_id
            raw_ids = team.pokemon_ids
            raw_anchor = team.anchor_pokemon_id
        else:
            eff_game_id = game_id
            raw_ids = tuple(pokemon_ids) if pokemon_ids is not None else ()
            raw_anchor = anchor_pokemon_id

        # 2. Enforce explicit, valid game context
        if not eff_game_id or not isinstance(eff_game_id, str) or not eff_game_id.strip():
            raise GameNotFoundError(str(eff_game_id))

        game_summary = GameCatalogService.get_game(session, eff_game_id)
        # Validate that rules profile can be resolved
        GameCatalogService.get_game_rule_profile(eff_game_id)
        canonical_game_id = game_summary.id

        # 3. Validate team size (1-6 members)
        if raw_ids is None or len(raw_ids) < cls.MIN_TEAM_SIZE:
            raise InvalidTeamSizeError(
                f"Team cannot be empty. A team must contain between {cls.MIN_TEAM_SIZE} "
                f"and {cls.MAX_TEAM_SIZE} Pokémon."
            )
        if len(raw_ids) > cls.MAX_TEAM_SIZE:
            raise InvalidTeamSizeError(
                f"Team cannot exceed {cls.MAX_TEAM_SIZE} Pokémon (got {len(raw_ids)})."
            )

        # 4. Canonicalize identifiers and enforce duplicate prevention
        seen_ids: set[str] = set()
        normalized_ids: list[str] = []

        for p_id in raw_ids:
            if not p_id or not isinstance(p_id, str) or not p_id.strip():
                raise PokemonNotFoundError(
                    str(p_id), message="Invalid empty Pokémon identifier in team."
                )

            norm_id = p_id.strip().lower()
            if norm_id in seen_ids:
                raise DuplicateTeamMemberError(
                    f"Duplicate Pokémon '{p_id}' in team. Teams cannot contain duplicate Pokémon."
                )
            seen_ids.add(norm_id)
            normalized_ids.append(norm_id)

        # 5. Validate optional anchor Pokémon
        norm_anchor: str | None = None
        if raw_anchor is not None and raw_anchor.strip() != "":
            candidate_anchor = raw_anchor.strip().lower()
            if candidate_anchor not in seen_ids:
                raise InvalidAnchorError(
                    f"Anchor Pokémon '{raw_anchor}' is not a member of the selected team."
                )
            norm_anchor = candidate_anchor

        # 6. Retrieve game-specific attributes and build immutable members
        validated_members: list[ValidatedTeamMember] = []
        for index, norm_id in enumerate(normalized_ids):
            slot = index + 1
            # Retrieve game-accurate details
            # (raises PokemonNotFoundError or PokemonUnavailableInGameError)
            detail = PokemonCatalogService.get_pokemon_details(
                session=session,
                game_id=canonical_game_id,
                pokemon_id=norm_id,
            )

            # Map elemental types to PokemonType enums
            member_types = tuple(PokemonType(t.type_id.lower()) for t in detail.types)

            # Preserve available abilities metadata without assuming active selection
            # Note: detail.abilities is already a tuple of PokemonAbilityInfo (id, name, is_hidden)
            is_anchor = norm_anchor is not None and detail.id == norm_anchor

            validated_members.append(
                ValidatedTeamMember(
                    slot=slot,
                    pokemon_id=detail.id,
                    dex_number=detail.dex_number,
                    name=detail.name,
                    species_name=detail.species_name,
                    form_name=detail.form_name,
                    types=member_types,
                    abilities=detail.abilities,
                    base_stats=detail.base_stats,
                    is_anchor=is_anchor,
                )
            )

        # 7. Return immutable ValidatedTeam
        return ValidatedTeam(
            game_id=canonical_game_id,
            members=tuple(validated_members),
            anchor_pokemon_id=norm_anchor,
        )
