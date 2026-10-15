class AppError(Exception):
    """Base exception for application domain errors."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GameNotFoundError(AppError):
    """Raised when a requested Pokémon game is not found or unsupported."""

    def __init__(self, game_id: str) -> None:
        super().__init__(f"Game '{game_id}' is not supported.", status_code=404)
        self.game_id = game_id


class PokemonNotFoundError(AppError):
    """Raised when a Pokémon is not found in the catalog."""

    def __init__(self, pokemon_id: str, message: str | None = None) -> None:
        msg = message or f"Pokemon '{pokemon_id}' was not found in the catalog."
        super().__init__(msg, status_code=404)
        self.pokemon_id = pokemon_id


class PokemonUnavailableInGameError(AppError):
    """Raised when a Pokémon exists in the catalog but is unavailable in the target game."""

    def __init__(self, pokemon_id: str, game_id: str) -> None:
        super().__init__(
            f"Pokemon '{pokemon_id}' is not available in game '{game_id}'.",
            status_code=404,
        )
        self.pokemon_id = pokemon_id
        self.game_id = game_id


class InvalidPaginationError(AppError):
    """Raised when pagination parameters (limit, offset) are invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class UnsupportedTypeError(AppError):
    """Raised when an elemental type is unsupported in the current game context."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class InvalidTypeMatchupError(AppError):
    """Raised when an invalid type matchup combination is evaluated."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
