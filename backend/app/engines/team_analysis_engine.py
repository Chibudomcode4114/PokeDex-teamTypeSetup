"""Team Analysis Engine: defensive matrix aggregation and STAB Type Coverage (Milestone 4).

This module implements deterministic, game-aware defensive team analysis (Milestone 4B).
Zero dependencies on FastAPI, SQLAlchemy, HTTP, databases, or UI.
"""

from __future__ import annotations

from app.core.errors import (
    DuplicateTeamMemberError,
    InvalidTeamSizeError,
    InvalidTypeMatchupError,
    TeamValidationError,
    UnsupportedTypeError,
)
from app.engines.matchup_engine import TypeMatchupEngine
from app.engines.matchup_engine import matchup_engine as default_matchup_engine
from app.engines.rules_engine import GameRulesEngine
from app.engines.rules_engine import rules_engine as default_rules_engine
from app.models.team import ValidatedTeam
from app.models.team_analysis import (
    DefensiveClassification,
    MemberDefensiveMatchup,
    SharedWeakness,
    SharedWeaknessMember,
    TeamDefensiveAnalysis,
    TypeDefenseAnalysis,
    classify_multiplier,
)


class TeamAnalysisEngine:
    """Pure domain engine for analyzing Pokémon team defensive matchups and synergies."""

    def __init__(
        self,
        rules_engine: GameRulesEngine | None = None,
        matchup_engine: TypeMatchupEngine | None = None,
    ) -> None:
        self._rules_engine = rules_engine or default_rules_engine
        self._matchup_engine = matchup_engine or default_matchup_engine

    def analyze_defenses(self, team: ValidatedTeam) -> TeamDefensiveAnalysis:
        """Calculate game-aware defensive type matchups and shared weaknesses for a validated team.

        Evaluation is strictly type-only in baseline M4B: no abilities are inferred, activated,
        or evaluated.

        Args:
            team: A fully validated Pokémon team instance.

        Returns:
            An immutable TeamDefensiveAnalysis result.

        Raises:
            TeamValidationError: If the team structure or slots are invalid.
            InvalidTeamSizeError: If the team size is not between 1 and 6 members.
            DuplicateTeamMemberError: If the team contains duplicate Pokémon identifiers.
            UnsupportedTypeError: If any team member has a type unsupported in the game.
            GameNotFoundError: If the team's game_id is unrecognized or unsupported.
        """
        # 1. Structural consistency validation
        if not isinstance(team, ValidatedTeam):
            raise TeamValidationError(
                f"Expected ValidatedTeam instance, got {type(team).__name__}."
            )

        num_members = len(team.members)
        if num_members < 1 or num_members > 6:
            raise InvalidTeamSizeError(
                f"Team must contain between 1 and 6 members, but has {num_members}."
            )

        # Enforce distinct, sequential 1-indexed slots (1..N)
        expected_slots = list(range(1, num_members + 1))
        actual_slots = [m.slot for m in team.members]
        if actual_slots != expected_slots:
            raise TeamValidationError(
                f"Team member slots are invalid or out of sequence: expected {expected_slots}, "
                f"got {actual_slots}."
            )

        # Enforce uniqueness of member identifiers
        seen_ids: set[str] = set()
        for member in team.members:
            norm_id = member.pokemon_id.strip().lower()
            if norm_id in seen_ids:
                raise DuplicateTeamMemberError(
                    f"Duplicate member '{member.pokemon_id}' found in team."
                )
            seen_ids.add(norm_id)

        # 2. Resolve authoritative game rule profile
        rule_profile = self._rules_engine.resolve(team.game_id)

        # Verify that all member types are valid and supported in this game
        for member in team.members:
            if not member.types or len(member.types) > 2:
                raise InvalidTypeMatchupError(
                    f"Member '{member.pokemon_id}' has invalid number of types: "
                    f"{len(member.types)}."
                )
            for t in member.types:
                if not rule_profile.is_type_supported(t):
                    raise UnsupportedTypeError(
                        f"Type '{t.value}' on '{member.pokemon_id}' is not supported in "
                        f"game '{rule_profile.game_id}'."
                    )

        # 3. Calculate defensive matchups for every attacking type supported by the game
        type_analyses: list[TypeDefenseAnalysis] = []
        shared_weaknesses: list[SharedWeakness] = []

        for attacking_type in rule_profile.supported_types:
            member_matchups: list[MemberDefensiveMatchup] = []
            weak_count = 0
            neutral_count = 0
            resistant_count = 0
            immune_count = 0

            for member in team.members:
                multiplier = self._matchup_engine.calculate_matchup(
                    attacking_type=attacking_type,
                    defending_types=member.types,
                    chart_context=rule_profile.type_chart_version,
                )
                classification = classify_multiplier(multiplier)

                if classification == DefensiveClassification.WEAK:
                    weak_count += 1
                elif classification == DefensiveClassification.NEUTRAL:
                    neutral_count += 1
                elif classification == DefensiveClassification.RESISTANT:
                    resistant_count += 1
                elif classification == DefensiveClassification.IMMUNE:
                    immune_count += 1

                member_matchups.append(
                    MemberDefensiveMatchup(
                        pokemon_id=member.pokemon_id,
                        slot=member.slot,
                        multiplier=multiplier,
                        classification=classification,
                    )
                )

            is_shared_weakness = weak_count >= 2

            type_analysis = TypeDefenseAnalysis(
                attacking_type=attacking_type,
                member_matchups=tuple(member_matchups),
                weak_count=weak_count,
                neutral_count=neutral_count,
                resistant_count=resistant_count,
                immune_count=immune_count,
                is_shared_weakness=is_shared_weakness,
            )
            type_analyses.append(type_analysis)

            # 4. Record shared weaknesses affecting 2 or more members
            if is_shared_weakness:
                affected_members = tuple(
                    SharedWeaknessMember(
                        pokemon_id=m.pokemon_id,
                        slot=m.slot,
                        multiplier=m.multiplier,
                    )
                    for m in member_matchups
                    if m.classification == DefensiveClassification.WEAK
                )
                shared_weaknesses.append(
                    SharedWeakness(
                        attacking_type=attacking_type,
                        count=weak_count,
                        members=affected_members,
                    )
                )

        return TeamDefensiveAnalysis(
            game_id=rule_profile.game_id,
            analysis_mode="type_only",
            type_chart_version=rule_profile.type_chart_version,
            type_matchups=tuple(type_analyses),
            shared_weaknesses=tuple(shared_weaknesses),
        )


# Global default instance
team_analysis_engine = TeamAnalysisEngine()
