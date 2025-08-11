import os
import time
from dotenv import load_dotenv

# Reuse the odds loader and DB connection from the main loader module
from scripts.init_data_load import load_game_lines_from_odds_api


def main() -> None:
    load_dotenv()
    try:
        interval_seconds = int(os.getenv("ODDS_POLL_SECONDS", "600"))  # default 10 minutes
    except Exception:
        interval_seconds = 600

    print(f"Starting odds snapshot loop. Interval={interval_seconds}s. Press Ctrl+C to stop.")
    while True:
        try:
            load_game_lines_from_odds_api()
        except KeyboardInterrupt:
            print("Stopping odds snapshot loop (KeyboardInterrupt)")
            break
        except Exception as e:
            print(f"Snapshot iteration failed: {e}")

        time.sleep(interval_seconds)


if __name__ == "__main__":
    main()

