"""Read practice settings exclusively from homework/.env, never the app's .env."""
from pathlib import Path


def load_homework_env() -> dict[str, str]:
    from dotenv import dotenv_values

    env_file = Path(__file__).resolve().with_name(".env")
    if not env_file.is_file():
        raise FileNotFoundError(
            "Create homework/.env from homework/.env.example and fill in your practice settings."
        )
    # Disable interpolation so ${NAME} cannot import values from the kernel's environment.
    values = dotenv_values(env_file, interpolate=False)
    return {key: value for key, value in values.items() if value is not None}
