import subprocess


def get_decks() -> list[str]:
    return [
        line[4:]
        for line in subprocess
        .run("apy", capture_output=True)
        .stdout.decode("utf-8")
        .split("Decks:")[1]
        .split("\n\n")[0]
        .split("\n")
    ]
