"""Module/frozen entry point; dispatch spawned workers before parsing GUI options."""

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()

    from datelier import main

    main()
