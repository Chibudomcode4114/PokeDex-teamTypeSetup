PokeDex TeamTypeMatchup

Project Planning, Software Requirements Specification (SRS) & Technical
Design --- Revised

Document purpose: This document defines the first practical version of
PokeDex TeamTypeMatchup, a game-aware Pokémon team-building and matchup
assistant. The selected Pokémon game is treated as part of the analysis
context so that Pokémon availability, abilities, moves, type rules and
other supported mechanics are interpreted according to the game the
player is actually playing.

## 1. Project Planning

### 1.1 Project Overview

PokeDex TeamTypeMatchup is a web-based guide that combines Pokémon
reference information with team building and matchup analysis. The user
first selects the specific Pokémon game they are playing. The system
then uses the rule profile for that game when presenting Pokémon data
and analysing a team. This avoids treating mechanics as if they were
identical across every title and generation.

### 1.2 Problem Statement

Players often move between different sources to check Pokémon types,
abilities, moves, stats, weaknesses and team coverage. The problem
becomes harder when information changes between games or generations. A
player may also want to build around a less-used Pokémon rather than
replace it with a stronger or more popular option. The project brings
these tasks into one place while keeping the selected game as the source
of context for the analysis.

### 1.3 Project Goals

-   Let the player select the exact supported Pokémon game before
    starting game-dependent analysis.

-   Provide a searchable Pokédex filtered to the selected game.

-   Show Pokémon types, abilities, stats and other supported information
    in the correct game context.

-   Allow users to create and edit a team of up to six Pokémon.

-   Calculate team-level weaknesses, resistances and immunities using
    the selected game rules.

-   Identify important coverage gaps and explain why they matter.

-   Recommend Pokémon that complement the chosen team rather than simply
    replacing less-used Pokémon with popular choices.

-   Explain why each recommendation fits the team.

-   Create an architecture that can support more game-specific mechanics
    without rewriting the whole application.

### 1.4 MVP Goals

The first MVP should prove one complete game-aware workflow rather than
attempt to model every battle mechanic at once:

-   Select a supported Pokémon game.

-   Load the rule profile and available Pokémon for that game.

-   Search and view Pokémon available in the selected game.

-   Display types, abilities, base stats and relevant matchup
    information for that game.

-   Create a six-Pokémon team.

-   Calculate the team type profile using the selected game context.

-   Flag repeated weaknesses and missing coverage.

-   Recommend a small set of compatible candidate Pokémon from the
    selected game.

-   Explain each recommendation using transparent rules.

### 1.5 Out of Scope for the First MVP

-   Live battle simulation.

-   Online multiplayer.

-   Trading or marketplace features.

-   AI-generated battle coaching.

-   Perfect competitive-tier prediction or meta rankings.

-   Modelling every obscure battle interaction in every game from day
    one.

-   Full move-set optimisation for every supported game.

-   User accounts unless persistent cloud teams become necessary.

### 1.6 Technical Feasibility

The project remains technically feasible if game support is introduced
in controlled stages. Most of the core MVP logic is deterministic. The
main additional challenge is versioned data: the backend must know which
rules and records apply to the selected game. A Game Rules Engine should
therefore sit before the matchup and recommendation logic.

-   Frontend: game selector, Pokédex, team builder, Pokémon details and
    analysis views.

-   Backend: API endpoints, game-context resolution, team analysis and
    recommendation logic.

-   Database: games, generations, Pokémon, game availability, types,
    abilities, ability versions, moves and rule profiles.

-   Game Rules Engine: resolves which mechanics and records apply to the
    selected game.

-   Type Matchup Engine: calculates type interactions under the selected
    rule profile.

-   Recommendation Engine: compares team gaps with candidate Pokémon
    available in the selected game.

### 1.7 Financial Feasibility

The MVP can still be built at low cost with open-source tools and a
public Pokémon data source or appropriately licensed dataset. The larger
cost is development time spent cleaning and validating game-specific
data. To keep this manageable, the first release should support a
limited set of games and expand after the architecture is proven.

| Resource \| MVP Approach \| Expected Cost \|

| --- \| --- \| --- \|

| Development tools \| VS Code, Git and open-source libraries \| Low or
  free \|

| Pokémon data \| Public API/dataset with terms checked before release
  \| Free initially \|

| Database \| Local PostgreSQL; free cloud tier if needed \| Low or free
  \|

| Hosting \| Free/low-cost prototype hosting \| Low \|

| Domain \| Optional for MVP \| Optional \|

| People \| Solo developer initially \| No external labour required \|

| Data validation \| Manual test cases for supported games \| Mainly
  development time \|

### 1.8 Resource Allocation

-   Product: define supported games, MVP boundaries and acceptance
    criteria.

-   Data: map each supported game to generation, Pokémon availability,
    abilities, moves and relevant rules.

-   Backend: implement game context, API, matchup engine and
    recommendations.

-   Frontend: implement game selection, search, team builder and
    analysis screens.

-   Testing: maintain game-specific test cases so mechanics from one
    title do not leak into another.

-   Documentation: record which mechanics are supported for each game
    and known limitations.

## 2. Software Requirements Specification (SRS)

### 2.1 Product Scope

The system will act as a game-aware Pokédex and team-building assistant.
Before game-dependent analysis begins, the player selects a supported
Pokémon game. The system uses that selection to determine available
Pokémon and the supported mechanics used by the Pokédex, matchup engine
and recommendation engine. The application remains advisory: the player
makes the final team decision.

### 2.2 User Types

-   Player/User --- selects a game, searches Pokémon, views
    game-specific information, builds teams and analyses coverage.

-   Administrator/Developer --- maintains game profiles, data mappings,
    rules and system configuration.

### 2.3 Functional Requirements

| ID \| Requirement \| Description \|

| --- \| --- \| --- \|

| FR-01 \| Game Selection \| The system shall require the user to select
  a supported Pokémon game before game-dependent Pokémon or team
  analysis. \|

| FR-02 \| Game Context \| The system shall associate the selected game
  with the current team session until the user changes it. \|

| FR-03 \| Rule Profile \| The system shall load the rule profile
  associated with the selected game. \|

| FR-04 \| Game Availability \| The system shall only present Pokémon
  and supported data that are valid for the selected game or clearly
  mark data that is outside that game. \|

| FR-05 \| Pokémon Search \| The system shall allow users to search for
  Pokémon within the selected game context. \|

| FR-06 \| Pokémon Details \| The system shall display game-relevant
  type, abilities, base stats and other supported data. \|

| FR-07 \| Ability Versioning \| Where an Ability effect differs between
  supported game versions, the system shall use the effect associated
  with the selected game. \|

| FR-08 \| Move Mechanics \| Where move behaviour or damage category
  differs between supported games, the system shall use the selected
  game rules when that mechanic is included in analysis. \|

| FR-09 \| Type Matchup \| The system shall calculate weaknesses,
  resistances and immunities using the type rules for the selected game.
  \|

| FR-10 \| Team Creation \| The system shall allow the user to add up to
  six Pokémon available in the selected game to a team. \|

| FR-11 \| Team Editing \| The user shall be able to remove or replace
  Pokémon in the team. \|

| FR-12 \| Team Analysis \| The system shall calculate the combined
  defensive type profile of the team. \|

| FR-13 \| Weakness Detection \| The system shall identify attacking
  types against which multiple team members are vulnerable. \|

| FR-14 \| Coverage Detection \| The system shall identify important
  coverage gaps using the mechanics supported by the current MVP. \|

| FR-15 \| Candidate Suggestions \| The system shall recommend candidate
  Pokémon that are available in the selected game and can address
  identified team gaps. \|

| FR-16 \| Recommendation Explanation \| The system shall show the main
  reasons each candidate was suggested. \|

| FR-17 \| Less-used Pokémon Support \| The recommendation process shall
  allow the player to keep a chosen Pokémon as a team anchor and build
  around it rather than automatically replacing it with a stronger
  alternative. \|

| FR-18 \| Game Change Handling \| When the selected game changes, the
  system shall revalidate the current team and identify members or data
  that are no longer valid in the new game context. \|

| FR-19 \| Unsupported Game Handling \| The system shall clearly
  identify unsupported games instead of silently applying rules from
  another title. \|

| FR-20 \| Team Persistence \| The MVP may use temporary browser/local
  storage to retain the current team without requiring an account. \|

### 2.4 Non-Functional Requirements

-   Usability: Game selection should be clear and should not require the
    player to know the generation number.

-   Accuracy: The application must not mix rules from different game
    profiles during an analysis.

-   Traceability: Game-dependent results should display the selected
    game so the user knows the context of the answer.

-   Performance: Common searches and team calculations should return
    quickly under normal conditions.

-   Maintainability: Game rules, Pokémon data and presentation code
    should be separated so a new game can be added without rewriting the
    interface.

-   Scalability: The schema should support additional games, mechanics,
    forms and rule versions.

-   Reliability: Invalid Pokémon, unavailable team members and
    incomplete version data should be handled gracefully.

-   Security: API endpoints should validate user input and keep
    credentials/server secrets private.

-   Accessibility: Core information should be keyboard navigable and
    should not depend only on colour.

### 2.5 Data Requirements

-   Game identifier, title, generation and release grouping.

-   Game rule profile and supported mechanic flags.

-   Pokémon identifier, name and form.

-   Pokémon availability by game.

-   Pokémon types by relevant version where necessary.

-   Abilities and versioned Ability effects.

-   Base statistics and version-specific values where applicable.

-   Moves, move types, power, accuracy and game availability when move
    analysis is enabled.

-   Move damage category/rules for supported games.

-   Type-effectiveness relationships by applicable rule set.

-   Optional later: encounter data, learnsets, items, roles, usage
    statistics and battle-format information.

### 2.6 Core User Flow

1.  User opens the application.

2.  User selects the specific Pokémon game being played.

3.  System loads the matching game rule profile.

4.  User searches for a Pokémon.

5.  System returns Pokémon valid for that game context.

6.  User opens a Pokémon and reviews its game-relevant information.

7.  User adds the Pokémon to a team.

8.  User adds up to five more Pokémon.

9.  System calculates the team profile using the selected game rules.

10. System highlights repeated weaknesses and gaps.

11. User requests suggestions.

12. System returns game-valid candidates with clear reasons for each
    suggestion.

### 2.7 Acceptance Criteria for MVP

-   A user can select a supported Pokémon game before analysis.

-   The selected game remains visible during team building and analysis.

-   Search results are filtered or validated against the selected game.

-   The system can demonstrate at least one mechanic whose treatment
    differs between two supported game profiles.

-   A user can create a team of up to six Pokémon valid for the selected
    game.

-   The system correctly calculates type effectiveness for the supported
    game rules.

-   The system shows repeated team weaknesses.

-   Recommendations only include valid candidates for the selected game.

-   The user can understand why a candidate was suggested.

-   Changing games triggers revalidation rather than silently retaining
    incompatible assumptions.

## 3. Technical Design

### 3.1 Proposed Architecture

A layered web architecture is recommended. The selected game is passed
with game-dependent requests. FastAPI resolves the game context and
invokes the Game Rules Engine before matchup or recommendation
calculations are performed.

-   Presentation Layer --- React + TypeScript frontend.

-   API/Application Layer --- FastAPI backend.

-   Game Context Layer --- Game Service and Game Rules Engine.

-   Analysis Layer --- Type Matchup Engine, Team Analysis Engine and
    Recommendation Engine.

-   Data Layer --- PostgreSQL for structured and versioned game data.

-   External Data Layer --- optional Pokémon API/dataset used for
    ingestion and updates.

### 3.2 Architecture Flow

User → Select Game → React Frontend → FastAPI → Game Rules Engine →
Analysis Engines → PostgreSQL

↘ Optional Pokémon Data Source

FastAPI is the application controller: it validates the request,
resolves the selected game, retrieves the correct versioned data, runs
the appropriate engines and returns a result that includes the game
context.

### 3.3 Main Backend Modules

-   Game Service --- retrieves supported games and their metadata.

-   Game Rules Engine --- resolves rule flags and versioned mechanics
    for the selected game.

-   Pokémon Service --- retrieves Pokémon data valid for the selected
    game.

-   Ability Service --- resolves the Ability and applicable
    effect/version.

-   Move Service --- resolves game-valid moves and applicable move
    mechanics when enabled.

-   Team Service --- creates and updates the current team in a game
    context.

-   Type Matchup Engine --- applies the type chart associated with the
    game rules.

-   Team Analysis Engine --- aggregates matchup results across the team.

-   Recommendation Engine --- finds game-valid candidates that address
    team gaps.

-   Data Validation Module --- prevents unsupported or incompatible
    records from entering analysis.

### 3.4 Database Design

The revised schema separates stable entities from game/version mappings.
This avoids duplicating an entire Pokémon record for every title while
still allowing game-specific behaviour.

| Table \| Important Fields / Purpose \|

| --- \| --- \|

| generations \| id, number, name \|

| games \| id, name, generation_id, version_group_id, supported \|

| game_rule_profiles \| game_id, physical_special_model,
  type_chart_version, mechanic flags \|

| pokemon \| id, name, species_id, form_name \|

| game_pokemon \| game_id, pokemon_id, available, notes \|

| types \| id, name \|

| pokemon_types \| pokemon_id, game/version scope, type_id, slot \|

| abilities \| id, name \|

| ability_versions \| ability_id, version_group/rule_profile,
  effect_text, effect_key \|

| pokemon_abilities \| pokemon_id, game/version scope, ability_id, slot,
  is_hidden \|

| moves \| id, name, type_id \|

| move_versions \| move_id, version_group/rule_profile, power, accuracy,
  damage_class, effect_key \|

| pokemon_moves \| pokemon_id, game/version scope, move_id, learn_method
  \|

| type_effectiveness \| rule_profile/type_chart_version,
  attacking_type_id, defending_type_id, multiplier \|

| teams \| id, name, game_id, created_at \|

| team_members \| team_id, pokemon_id, slot \|

### 3.5 Game Rules Engine

The Game Rules Engine is the first game-dependent decision point in the
backend. It receives a game ID and returns the rule profile used by the
other engines. The profile can include the applicable type chart,
damage-category model, supported mechanics and version group used to
resolve Ability and move effects.

This design keeps rules out of the UI and avoids scattering checks such
as "if generation is X" throughout the codebase. New games can be mapped
to existing rule profiles when their relevant mechanics are the same,
while exceptions can be versioned separately.

### 3.6 Type Matchup Engine

The type engine should use versioned lookup data rather than a single
universal type chart. For each attacking and defending type it retrieves
a multiplier such as 0x, 0.5x, 1x or 2x from the rule profile. Dual-type
multipliers are combined. This allows the system to respect type-chart
changes between supported game eras.

### 3.7 Recommendation Engine

The first recommendation engine should remain rule-based and
explainable.

1.  Analyse the current team under the selected game profile.

2.  Identify repeated weaknesses and uncovered gaps.

3.  Build a candidate pool containing Pokémon available in that game.

4.  Compare candidate types, supported Ability effects and defined roles
    against the gaps.

5.  Avoid candidates that unnecessarily duplicate major existing
    weaknesses where possible.

6.  Preserve any Pokémon the user has marked as a team anchor.

7.  Return a shortlist with reasons tied to the selected game rather
    than an unexplained score.

### 3.8 User Interface Design

-   Game Selection Screen/Control --- choose the exact supported game by
    title; generation can be displayed as supporting information.

-   Home/Search Screen --- search within the active game context.

-   Pokémon Detail Screen --- show the active game and the Pokémon
    information applicable to it.

-   Team Builder Screen --- six team slots, game indicator and
    add/remove/replace controls.

-   Team Analysis Screen --- weaknesses, resistances, immunities and
    coverage gaps under the active rules.

-   Suggestions Screen --- game-valid recommendations with explanations.

-   Change Game Flow --- warn the user that the current team will be
    revalidated when switching games.

### 3.9 UI Design Principles

-   Keep the selected game visible during game-dependent analysis.

-   Ask for the game title, not only the generation number.

-   Explain unavailable Pokémon or mechanics instead of silently hiding
    inconsistencies.

-   Use icons and labels together rather than relying on colour alone.

-   Show the reasoning behind recommendations.

-   Allow advanced mechanics to be expanded rather than overwhelming
    casual players.

### 3.10 Example API Endpoints

| Method \| Endpoint \| Purpose \|

| --- \| --- \| --- \|

| GET \| /games \| List supported games \|

| GET \| /games/{game_id}/rules \| Get the resolved game rule profile \|

| GET \| /pokemon?game_id={id}&search=pika \| Search Pokémon in a game
  context \|

| GET \| /pokemon/{id}?game_id={id} \| Get game-aware Pokémon details \|

| POST \| /teams \| Create a team with a game_id \|

| POST \| /teams/{id}/members \| Add a game-valid Pokémon \|

| PATCH \| /teams/{id}/game \| Change game and revalidate team \|

| GET \| /teams/{id}/analysis \| Calculate game-aware team matchup \|

| GET \| /teams/{id}/recommendations \| Return game-valid candidate
  Pokémon \|

### 3.11 Suggested Technology Stack

| Area \| Technology \| Reason \|

| --- \| --- \| --- \|

| Frontend \| React + TypeScript \| Good fit for interactive game
  selection and team building \|

| Backend \| FastAPI + Python \| Clear API structure and suitable for
  rule engines \|

| Database \| PostgreSQL \| Strong relational model for versioned game
  data \|

| ORM \| SQLAlchemy \| Keeps relational access organised \|

| Validation \| Pydantic \| Validates game context and API payloads \|

| Version Control \| Git + GitHub \| Tracks code, schema and rule
  changes \|

| Testing \| Pytest + frontend tests \| Supports game-specific
  regression tests \|

| Deployment \| Low-cost cloud hosting \| Suitable for an MVP \|

### 3.12 Development Phases

1.  Phase 1 --- Choose a small set of supported games and define the
    mechanics the MVP will model.

2.  Phase 2 --- Build the games, rule profiles and versioned data
    schema.

3.  Phase 3 --- Ingest and validate Pokémon, Ability, type and required
    move data.

4.  Phase 4 --- Build the Game Rules Engine and automated rule-profile
    tests.

5.  Phase 5 --- Build and test the version-aware Type Matchup Engine.

6.  Phase 6 --- Build game selection, Pokémon search and detail UI.

7.  Phase 7 --- Build team creation, revalidation and team analysis.

8.  Phase 8 --- Build the rule-based recommendation engine.

9.  Phase 9 --- Run cross-game regression tests, polish the UI and
    deploy.

## 4. Product Decisions and Scope Controls

The game-selection decision is now resolved: users should select the
exact supported game they are playing, and that selection becomes part
of every game-dependent analysis. The remaining decisions are mainly
scope controls for the first release:

-   Which specific games will be supported in version 1? A small
    representative set is safer than every title at launch.

-   Will the MVP target casual in-game team building first, competitive
    formats first, or provide separate modes?

-   Which game-specific mechanics are required for version 1 beyond
    types and Abilities?

-   At what stage should move-set analysis become part of
    recommendations?

-   How will "less-used" be defined if usage/popularity becomes a
    filter?

-   How should regional, alternate and battle-only forms be represented?

-   Which data source(s) will be used and what are their
    licensing/attribution requirements?

-   Will teams remain local or later be saved to user accounts?

## 5. Recommended MVP Boundary

The project should not attempt to perfectly simulate every Pokémon title
in its first release. The architecture should be game-aware from day
one, but the data and mechanics can be added game by game.

SELECT GAME → LOAD RULE PROFILE → SEARCH POKÉMON → BUILD TEAM → ANALYSE
MATCHUPS → FIND TEAM GAP → GET GAME-AWARE EXPLAINED SUGGESTIONS

A strong MVP can support a deliberately limited set of games while
proving that switching games changes the data or analysis correctly.
Once that foundation works, more titles, move mechanics, Ability
interactions, items, battle formats and advanced recommendations can be
added without changing the core architecture.

## 6. Design Principle

The application should not answer a game-dependent question about what a
Pokémon, Ability, move or team does without first knowing which
supported game rules apply. Game context is therefore a core input to
the system, not an optional preference.
