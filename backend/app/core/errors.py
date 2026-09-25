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


class PokemonNotFoundError(AppError):
    """Raised when a Pokémon is not found within the game context."""

    def __init__(self, pokemon_id: str, game_id: str) -> None:
        message = f"Pokemon '{pokemon_id}' is not found in game '{game_id}'."
        super().__init__(message, status_code=404)


class UnsupportedTypeError(AppError):
    """Raised when an elemental type is unsupported in the current game context."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class InvalidTypeMatchupError(AppError):
    """Raised when an invalid type matchup combination is evaluated."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
