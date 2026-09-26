import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.orm import (
    Ability,
    BaseStat,
    ElementType,
    Game,
    GamePokemon,
    GameRuleProfileModel,
    Generation,
    Pokemon,
    PokemonAbilityAssignment,
    PokemonTypeAssignment,
    TypeChartEntry,
)


class TestDatabaseSchema:
    """Test suite verifying relational schema definitions, constraints, and relationships."""

    def test_all_required_tables_exist(self, db_session: Session) -> None:
        """Verify that all 11 required catalog tables are created in the database."""
        inspector = inspect(db_session.bind)
        table_names = set(inspector.get_table_names())

        expected_tables = {
            "generations",
            "games",
            "game_rule_profiles",
            "types",
            "type_chart_entries",
            "pokemon",
            "game_pokemon",
            "pokemon_types",
            "abilities",
            "pokemon_abilities",
            "base_stats",
        }

        assert expected_tables.issubset(table_names)

    def test_generation_number_exists_and_unique(self, db_session: Session) -> None:
        """Verify that generation number exists as an integer and uniqueness is enforced."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        gen6 = Generation(id="gen-6", number=6, name="Generation VI")
        db_session.add_all([gen3, gen6])
        db_session.flush()

        assert gen3.number == 3
        assert gen6.number == 6

        # Attempt to insert a duplicate generation number (3)
        gen_duplicate = Generation(id="gen-3-dup", number=3, name="Duplicate Gen III")
        db_session.add(gen_duplicate)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_game_generation_relationship(self, db_session: Session) -> None:
        """Verify relationship between Game and Generation."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        game = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        db_session.add_all([gen3, game])
        db_session.flush()

        # Query back and verify navigation
        fetched_game = db_session.get(Game, "firered")
        assert fetched_game is not None
        assert fetched_game.generation.number == 3
        assert fetched_game in gen3.games

    def test_game_rule_profile_relationship(self, db_session: Session) -> None:
        """Verify GameRuleProfile to Game one-to-one relationship."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        game = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        profile = GameRuleProfileModel(
            game_id="firered",
            type_chart_version="gen2_5",
            has_fairy_type=False,
            steel_resists_dark_ghost=True,
        )
        db_session.add_all([gen3, game, profile])
        db_session.flush()

        fetched_game = db_session.get(Game, "firered")
        assert fetched_game is not None
        assert fetched_game.rule_profile is not None
        assert fetched_game.rule_profile.type_chart_version == "gen2_5"
        assert fetched_game.rule_profile.has_fairy_type is False
        assert fetched_game.rule_profile.game.id == "firered"

    def test_pokemon_game_availability_association(self, db_session: Session) -> None:
        """Verify associating a Pokémon with a supported game."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        game = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        poke = Pokemon(
            id="pikachu",
            dex_number=25,
            name="Pikachu",
            species_name="pikachu",
            form_name=None,
        )
        availability = GamePokemon(
            game_id="firered",
            pokemon_id="pikachu",
            is_available=True,
        )
        db_session.add_all([gen3, game, poke, availability])
        db_session.flush()

        fetched_poke = db_session.get(Pokemon, "pikachu")
        assert fetched_poke is not None
        assert len(fetched_poke.game_availabilities) == 1
        assert fetched_poke.game_availabilities[0].game.title == "Pokémon FireRed"
        assert fetched_poke.game_availabilities[0].is_available is True

    def test_pokemon_types_vary_between_firered_and_pokemon_x(self, db_session: Session) -> None:
        """Verify Clefairy is Normal in FireRed (Gen 3) and Fairy in Pokémon X (Gen 6)."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        gen6 = Generation(id="gen-6", number=6, name="Generation VI")
        firered = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        pokemon_x = Game(
            id="pokemon-x",
            title="Pokémon X",
            generation_id="gen-6",
            version_group="x-y",
            is_supported=True,
        )
        normal_type = ElementType(id="normal", name="Normal")
        fairy_type = ElementType(id="fairy", name="Fairy")
        clefairy = Pokemon(
            id="clefairy",
            dex_number=35,
            name="Clefairy",
            species_name="clefairy",
            form_name=None,
        )
        # Gen 3: Pure Normal in FireRed
        clefairy_fr = PokemonTypeAssignment(
            pokemon_id="clefairy",
            game_id="firered",
            type_id="normal",
            slot=1,
        )
        # Gen 6: Pure Fairy in Pokémon X
        clefairy_x = PokemonTypeAssignment(
            pokemon_id="clefairy",
            game_id="pokemon-x",
            type_id="fairy",
            slot=1,
        )
        db_session.add_all([
            gen3,
            gen6,
            firered,
            pokemon_x,
            normal_type,
            fairy_type,
            clefairy,
            clefairy_fr,
            clefairy_x,
        ])
        db_session.flush()

        fetched = db_session.get(Pokemon, "clefairy")
        assert fetched is not None
        assert len(fetched.type_assignments) == 2

        assignments_by_game = {t.game_id: t.type_id for t in fetched.type_assignments}
        assert assignments_by_game["firered"] == "normal"
        assert assignments_by_game["pokemon-x"] == "fairy"

        # Verify relationship from Game to type_assignments
        fetched_fr = db_session.get(Game, "firered")
        assert fetched_fr is not None
        assert len(fetched_fr.type_assignments) == 1
        assert fetched_fr.type_assignments[0].pokemon_id == "clefairy"

    def test_duplicate_pokemon_type_slot_rejected(self, db_session: Session) -> None:
        """Verify duplicate slot in the same game context is rejected."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        game = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        normal_type = ElementType(id="normal", name="Normal")
        fire_type = ElementType(id="fire", name="Fire")
        poke = Pokemon(
            id="eevee",
            dex_number=133,
            name="Eevee",
            species_name="eevee",
            form_name=None,
        )
        slot1_a = PokemonTypeAssignment(
            pokemon_id="eevee",
            game_id="firered",
            type_id="normal",
            slot=1,
        )
        slot1_b = PokemonTypeAssignment(
            pokemon_id="eevee",
            game_id="firered",
            type_id="fire",
            slot=1,  # Duplicate slot 1 in same game!
        )
        db_session.add_all([gen3, game, normal_type, fire_type, poke, slot1_a, slot1_b])
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_duplicate_type_chart_entry_rejected(self, db_session: Session) -> None:
        """Verify duplicate type chart entry (chart + attacker + defender) is rejected."""
        water = ElementType(id="water", name="Water")
        fire = ElementType(id="fire", name="Fire")
        entry1 = TypeChartEntry(
            chart_version="gen6_plus",
            attacker_type_id="water",
            defender_type_id="fire",
            multiplier=2.0,
        )
        entry2 = TypeChartEntry(
            chart_version="gen6_plus",
            attacker_type_id="water",
            defender_type_id="fire",
            multiplier=2.0,  # Duplicate
        )
        db_session.add_all([water, fire, entry1, entry2])
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_pokemon_abilities_vary_between_games(self, db_session: Session) -> None:
        """Verify abilities can vary between games (e.g. Gengar in FireRed vs Pokémon Sun)."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        gen7 = Generation(id="gen-7", number=7, name="Generation VII")
        firered = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        sun = Game(
            id="sun",
            title="Pokémon Sun",
            generation_id="gen-7",
            version_group="sun-moon",
            is_supported=False,
        )
        levitate = Ability(id="levitate", name="Levitate")
        cursed_body = Ability(id="cursed-body", name="Cursed Body")
        gengar = Pokemon(
            id="gengar",
            dex_number=94,
            name="Gengar",
            species_name="gengar",
            form_name=None,
        )
        # Gen 3: Levitate in FireRed
        gengar_fr = PokemonAbilityAssignment(
            pokemon_id="gengar",
            game_id="firered",
            ability_id="levitate",
            is_hidden=False,
        )
        # Gen 7: Cursed Body in Sun
        gengar_sun = PokemonAbilityAssignment(
            pokemon_id="gengar",
            game_id="sun",
            ability_id="cursed-body",
            is_hidden=False,
        )
        db_session.add_all([
            gen3,
            gen7,
            firered,
            sun,
            levitate,
            cursed_body,
            gengar,
            gengar_fr,
            gengar_sun,
        ])
        db_session.flush()

        fetched = db_session.get(Pokemon, "gengar")
        assert fetched is not None
        assert len(fetched.ability_assignments) == 2

        abilities_by_game = {a.game_id: a.ability_id for a in fetched.ability_assignments}
        assert abilities_by_game["firered"] == "levitate"
        assert abilities_by_game["sun"] == "cursed-body"

        # Verify relationship from Game to ability_assignments
        fetched_fr = db_session.get(Game, "firered")
        assert fetched_fr is not None
        assert len(fetched_fr.ability_assignments) == 1
        assert fetched_fr.ability_assignments[0].ability_id == "levitate"

    def test_duplicate_pokemon_ability_rejected(self, db_session: Session) -> None:
        """Verify duplicate ability assignment for the same Pokémon and game is rejected."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        game = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        levitate = Ability(id="levitate", name="Levitate")
        poke = Pokemon(
            id="gengar",
            dex_number=94,
            name="Gengar",
            species_name="gengar",
            form_name=None,
        )
        a1 = PokemonAbilityAssignment(
            pokemon_id="gengar",
            game_id="firered",
            ability_id="levitate",
            is_hidden=False,
        )
        a2 = PokemonAbilityAssignment(
            pokemon_id="gengar",
            game_id="firered",
            ability_id="levitate",
            is_hidden=True,  # Duplicate (pokemon_id, game_id, ability_id)
        )
        db_session.add_all([gen3, game, levitate, poke, a1, a2])
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_base_stats_vary_between_games(self, db_session: Session) -> None:
        """Verify base stats can vary across games (e.g. Pidgeot Speed buff in Gen 6)."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        gen6 = Generation(id="gen-6", number=6, name="Generation VI")
        firered = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        pokemon_x = Game(
            id="pokemon-x",
            title="Pokémon X",
            generation_id="gen-6",
            version_group="x-y",
            is_supported=True,
        )
        pidgeot = Pokemon(
            id="pidgeot",
            dex_number=18,
            name="Pidgeot",
            species_name="pidgeot",
            form_name=None,
        )
        stats_fr = BaseStat(
            pokemon_id="pidgeot",
            game_id="firered",
            hp=83,
            atk=80,
            def_=75,
            spa=70,
            spd=70,
            spe=91,  # Gen 3-5 Speed = 91
        )
        stats_x = BaseStat(
            pokemon_id="pidgeot",
            game_id="pokemon-x",
            hp=83,
            atk=80,
            def_=75,
            spa=70,
            spd=70,
            spe=101,  # Gen 6+ Speed = 101 (+10 buff)
        )
        db_session.add_all([gen3, gen6, firered, pokemon_x, pidgeot, stats_fr, stats_x])
        db_session.flush()

        fetched = db_session.get(Pokemon, "pidgeot")
        assert fetched is not None
        assert len(fetched.base_stats) == 2

        spe_by_game = {s.game_id: s.spe for s in fetched.base_stats}
        assert spe_by_game["firered"] == 91
        assert spe_by_game["pokemon-x"] == 101

        # Verify relationship from Game to base_stats
        fetched_x = db_session.get(Game, "pokemon-x")
        assert fetched_x is not None
        assert len(fetched_x.base_stats) == 1
        assert fetched_x.base_stats[0].spe == 101

    def test_duplicate_base_stats_rejected(self, db_session: Session) -> None:
        """Verify duplicate base stats for same Pokémon and game is rejected."""
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        game = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        poke = Pokemon(
            id="pidgeot",
            dex_number=18,
            name="Pidgeot",
            species_name="pidgeot",
            form_name=None,
        )
        s1 = BaseStat(
            pokemon_id="pidgeot",
            game_id="firered",
            hp=83,
            atk=80,
            def_=75,
            spa=70,
            spd=70,
            spe=91,
        )
        s2 = BaseStat(
            pokemon_id="pidgeot",
            game_id="firered",
            hp=83,
            atk=80,
            def_=75,
            spa=70,
            spd=70,
            spe=91,  # Duplicate (pokemon_id, game_id)
        )
        db_session.add_all([gen3, game, poke, s1, s2])
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

    def test_foreign_key_constraints_enforced(self, db_session: Session) -> None:
        """Verify foreign key constraint violations raise IntegrityError."""
        # 1. Invalid generation_id on Game
        invalid_game = Game(
            id="invalid_game",
            title="Nonexistent Game",
            generation_id="nonexistent_gen_id",
            version_group="invalid",
            is_supported=False,
        )
        db_session.add(invalid_game)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

        # Seed valid generation, game, and pokemon for subsequent FK tests
        gen3 = Generation(id="gen-3", number=3, name="Generation III")
        game = Game(
            id="firered",
            title="Pokémon FireRed",
            generation_id="gen-3",
            version_group="firered-leafgreen",
            is_supported=True,
        )
        normal_type = ElementType(id="normal", name="Normal")
        levitate = Ability(id="levitate", name="Levitate")
        poke = Pokemon(
            id="pikachu",
            dex_number=25,
            name="Pikachu",
            species_name="pikachu",
            form_name=None,
        )
        db_session.add_all([gen3, game, normal_type, levitate, poke])
        db_session.flush()

        # 2. Invalid game_id on PokemonTypeAssignment
        invalid_type_assign = PokemonTypeAssignment(
            pokemon_id="pikachu",
            game_id="nonexistent_game",
            type_id="normal",
            slot=1,
        )
        db_session.add(invalid_type_assign)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

        # 3. Invalid game_id on PokemonAbilityAssignment
        invalid_ability_assign = PokemonAbilityAssignment(
            pokemon_id="pikachu",
            game_id="nonexistent_game",
            ability_id="levitate",
            is_hidden=False,
        )
        db_session.add(invalid_ability_assign)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()

        # 4. Invalid game_id on BaseStat
        invalid_stat = BaseStat(
            pokemon_id="pikachu",
            game_id="nonexistent_game",
            hp=35,
            atk=55,
            def_=40,
            spa=50,
            spd=50,
            spe=90,
        )
        db_session.add(invalid_stat)
        with pytest.raises(IntegrityError):
            db_session.flush()
        db_session.rollback()
