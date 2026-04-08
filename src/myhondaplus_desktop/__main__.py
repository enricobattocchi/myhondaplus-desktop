"""Entrypoint for module and packaged execution."""


def _load_main():
    try:
        from .app import main as app_main
    except ImportError:
        from myhondaplus_desktop.app import main as app_main
    return app_main


def run():
    _load_main()()


if __name__ == "__main__":
    run()
