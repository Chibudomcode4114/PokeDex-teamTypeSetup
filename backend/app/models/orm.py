"""SQLAlchemy 2.0 ORM models for game-aware Pokémon catalog data.

These models represent persistence only and are decoupled from runtime calculation domain models.
"""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Generation(Base):
    """Pokémon generation entity."""

    __tablename__ = "generations"
    __table_args__ = (
        UniqueConstraint("number", name="uq_generation_number"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    number: Mapped[int] = mapped_column(Integer, unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)

    games: Mapped[list["Game"]] = relationship(
        back_populates="generation", cascade="all, delete-orphan"
    )


class Game(Base):
    """Pokémon game entity."""

    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    generation_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("generations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_group: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    generation: Mapped["Generation"] = relationship(back_populates="games")
    rule_profile: Mapped["GameRuleProfileModel | None"] = relationship(
        back_populates="game", uselist=False, cascade="all, delete-orphan"
    )
    game_pokemon: Mapped[list["GamePokemon"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    type_assignments: Mapped[list["PokemonTypeAssignment"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    ability_assignments: Mapped[list["PokemonAbilityAssignment"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )
    base_stats: Mapped[list["BaseStat"]] = relationship(
        back_populates="game", cascade="all, delete-orphan"
    )


class GameRuleProfileModel(Base):
    """Relational representation of game rule parameters and flags.

    Named GameRuleProfileModel to avoid colliding with pure domain GameRuleProfile.
    """

    __tablename__ = "game_rule_profiles"

    game_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("games.id", ondelete="CASCADE"), primary_key=True
    )
    type_chart_version: Mapped[str] = mapped_column(String(32), nullable=False)
    has_fairy_type: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    steel_resists_dark_ghost: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    game: Mapped["Game"] = relationship(back_populates="rule_profile")


class ElementType(Base):
    """Elemental type entity (e.g. Fire, Water, Steel).

    Named ElementType to avoid shadowing Python's builtin or typing.Type.
    """

    __tablename__ = "types"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)


class TypeChartEntry(Base):
    """Type chart matrix entry mapping attacking vs defending types to damage multiplier."""

    __tablename__ = "type_chart_entries"
    __table_args__ = (
        UniqueConstraint(
            "chart_version",
            "attacker_type_id",
            "defender_type_id",
            name="uq_type_chart_entry",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chart_version: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attacker_type_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    defender_type_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    multiplier: Mapped[float] = mapped_column(Float, nullable=False)

    attacker_type: Mapped["ElementType"] = relationship(foreign_keys=[attacker_type_id])
    defender_type: Mapped["ElementType"] = relationship(foreign_keys=[defender_type_id])


class Pokemon(Base):
    """Core Pokémon species/form entity."""

    __tablename__ = "pokemon"
    __table_args__ = (
        UniqueConstraint("species_name", "form_name", name="uq_pokemon_species_form"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dex_number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    species_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    form_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    game_availabilities: Mapped[list["GamePokemon"]] = relationship(
        back_populates="pokemon", cascade="all, delete-orphan"
    )
    type_assignments: Mapped[list["PokemonTypeAssignment"]] = relationship(
        back_populates="pokemon", cascade="all, delete-orphan"
    )
    ability_assignments: Mapped[list["PokemonAbilityAssignment"]] = relationship(
        back_populates="pokemon", cascade="all, delete-orphan"
    )
    base_stats: Mapped[list["BaseStat"]] = relationship(
        back_populates="pokemon", cascade="all, delete-orphan"
    )


class GamePokemon(Base):
    """Game-specific Pokémon availability association."""

    __tablename__ = "game_pokemon"
    __table_args__ = (
        UniqueConstraint("game_id", "pokemon_id", name="uq_game_pokemon"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    game_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pokemon_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pokemon.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    game: Mapped["Game"] = relationship(back_populates="game_pokemon")
    pokemon: Mapped["Pokemon"] = relationship(back_populates="game_availabilities")


class PokemonTypeAssignment(Base):
    """Game-scoped typing assignment for a Pokémon.

    Supports Pokémon whose types change across games
    (e.g. Clefairy Normal in FireRed -> Fairy in Pokémon X).
    """

    __tablename__ = "pokemon_types"
    __table_args__ = (
        UniqueConstraint(
            "pokemon_id",
            "game_id",
            "slot",
            name="uq_pokemon_type_slot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pokemon_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pokemon.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("types.id", ondelete="CASCADE"), nullable=False, index=True
    )
    slot: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 for primary, 2 for secondary

    pokemon: Mapped["Pokemon"] = relationship(back_populates="type_assignments")
    game: Mapped["Game"] = relationship(back_populates="type_assignments")
    type: Mapped["ElementType"] = relationship()


class Ability(Base):
    """Pokémon ability entity."""

    __tablename__ = "abilities"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)

    pokemon_assignments: Mapped[list["PokemonAbilityAssignment"]] = relationship(
        back_populates="ability", cascade="all, delete-orphan"
    )


class PokemonAbilityAssignment(Base):
    """Game-scoped ability assignment for a Pokémon."""

    __tablename__ = "pokemon_abilities"
    __table_args__ = (
        UniqueConstraint(
            "pokemon_id",
            "game_id",
            "ability_id",
            name="uq_pokemon_ability",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pokemon_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pokemon.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ability_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("abilities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    pokemon: Mapped["Pokemon"] = relationship(back_populates="ability_assignments")
    game: Mapped["Game"] = relationship(back_populates="ability_assignments")
    ability: Mapped["Ability"] = relationship(back_populates="pokemon_assignments")


class BaseStat(Base):
    """Game-scoped base stats for a Pokémon."""

    __tablename__ = "base_stats"
    __table_args__ = (
        UniqueConstraint(
            "pokemon_id",
            "game_id",
            name="uq_pokemon_base_stats",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pokemon_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("pokemon.id", ondelete="CASCADE"), nullable=False, index=True
    )
    game_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("games.id", ondelete="CASCADE"), nullable=False, index=True
    )
    hp: Mapped[int] = mapped_column(Integer, nullable=False)
    atk: Mapped[int] = mapped_column(Integer, nullable=False)
    def_: Mapped[int] = mapped_column("def", Integer, nullable=False)
    spa: Mapped[int] = mapped_column(Integer, nullable=False)
    spd: Mapped[int] = mapped_column(Integer, nullable=False)
    spe: Mapped[int] = mapped_column(Integer, nullable=False)

    pokemon: Mapped["Pokemon"] = relationship(back_populates="base_stats")
    game: Mapped["Game"] = relationship(back_populates="base_stats")
