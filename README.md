# PokeDex TeamTypeMatchup

PokeDex TeamTypeMatchup is a game-aware Pokémon team-building and
matchup assistant.

The project is designed to help players understand the Pokémon available
in the specific game they are playing, inspect types, abilities and
stats, build a team of up to six Pokémon, identify weaknesses and
coverage gaps, and receive explainable team suggestions.

A key goal is to support players who want to use less-popular or
traditionally "weak" Pokémon rather than simply recommending the Pokémon
with the highest stats.

## Core Idea

The application should not answer:

> What does this Pokémon do?

without first considering:

> Which Pokémon game is the player using?

The selected game determines the rules and data used by the rest of the
system. This matters because Pokémon availability, abilities, moves,
type mechanics and battle mechanics have changed across games and
generations.

The main application flow is:

``` text
SELECT GAME
    ↓
LOAD GAME RULE PROFILE
    ↓
SEARCH POKÉMON
    ↓
BUILD TEAM
    ↓
ANALYSE MATCHUPS
    ↓
IDENTIFY TEAM GAPS
    ↓
GET EXPLAINED SUGGESTIONS
```

## MVP Features

The first version of the application is intended to support:

-   Pokémon game selection
-   Pokémon search
-   Pokémon details
-   Type, ability and base-stat information
-   Teams of up to six Pokémon
-   Game-aware type matchup calculations
-   Team weakness, resistance and immunity analysis
-   Detection of repeated weaknesses and coverage gaps
-   Rule-based Pokémon recommendations
-   Human-readable explanations for recommendations
-   Support for less-used Pokémon when they provide useful team synergy

## Proposed Technology Stack

### Frontend

-   React
-   TypeScript

### Backend

-   Python
-   FastAPI
-   Pydantic
-   SQLAlchemy

### Database

-   PostgreSQL

### External Data

-   PokeAPI

PokeAPI supplies Pokémon-related source data. It should not be treated
as the application's rules or recommendation engine.

The intended flow is:

``` text
PokeAPI
   ↓
PokeAPI Service / Data Importer
   ↓
Normalised Application Data
   ↓
PostgreSQL
   ↓
Game Rules Engine
   ↓
Type Matchup / Team Analysis
   ↓
Recommendation Engine
```

The React frontend should communicate with the FastAPI backend rather
than calling PokeAPI directly.

## Planned Backend Structure

``` text
backend/
├── api/
├── models/
├── schemas/
├── services/
│   ├── pokeapi_service.py
│   ├── pokemon_service.py
│   └── game_service.py
├── engines/
│   ├── game_rules.py
│   ├── type_matchup.py
│   ├── team_analysis.py
│   └── recommendation.py
├── tests/
└── main.py
```

The exact structure may change as implementation begins, but the main
architectural boundaries should remain clear.

## Main System Components

### Game Rules Engine

Provides the rule context for the selected game. Other analysis
components should use this context instead of independently deciding
which generation rules apply.

### Pokédex/Data Service

Retrieves and normalises Pokémon, type, ability, move, version and
generation data.

### Type Matchup Engine

Calculates weaknesses, resistances, immunities and neutral interactions
according to the selected game's type rules.

### Team Analysis Engine

Combines individual Pokémon matchup information to identify team-wide
weaknesses, resistances, immunities and gaps.

### Recommendation Engine

Uses the selected game and team analysis to suggest Pokémon that improve
team synergy.

The MVP recommendation system should be deterministic and rule-based. It
should not simply rank candidates by base-stat total.

## Development Approach

Development should be completed in small vertical slices rather than
attempting to build the entire backend before connecting it to the
frontend.

Suggested order:

1.  Project foundation
2.  PokeAPI data mapping and integration
3.  Game selection and Game Rules Engine
4.  Pokémon search and details
5.  Type Matchup Engine
6.  Team Builder
7.  Team Analysis Engine
8.  Recommendation Engine
9.  End-to-end testing
10. UI polish and deployment

The first supported game should work end-to-end before additional games
are introduced.

## Documentation

Project documentation should live in the `docs/` directory.

Recommended documents:

``` text
docs/
├── REQUIREMENTS.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── POKEAPI_MAPPING.md
├── GAME_RULES.md
└── TEST_PLAN.md
```

`REQUIREMENTS.md` should be treated as the main product requirements
source of truth.

Before making major architectural changes, implementation work should be
checked against the requirements and architecture documentation.

## Working With Codex

When using Codex, avoid asking it to build the complete application in a
single task.

A useful starting instruction is:

``` text
Read docs/REQUIREMENTS.md completely before making changes.

Treat it as the product source of truth.

Break requested work into small implementation tasks.
Keep game rules, data access, API routes and analysis logic separate.
Do not add major features outside the requirements without identifying
them as proposals.

Run relevant tests after implementation and report any requirements
that are incomplete or ambiguous.
```

Each major engine should have independent tests.

## PokeAPI Integration

Before implementing the full integration, document how PokeAPI resources
map to the application's data model.

Pay particular attention to version-specific information including:

-   versions and version groups
-   generations
-   abilities and effect changes
-   moves
-   move learn methods
-   historical type information
-   game-specific Pokémon availability

Any game rule required by the application that cannot be reliably
derived from PokeAPI should be explicitly maintained by the
application's Game Rules layer.

## Project Status

**Status:** Planning / pre-MVP development

The current focus is defining the architecture, mapping PokeAPI data and
implementing the first supported game end-to-end.

## Disclaimer

This is an independent fan-made software project. Pokémon and related
names, characters and assets are trademarks and intellectual property of
their respective owners. This project is not affiliated with or endorsed
by Nintendo, Game Freak or The Pokémon Company.
