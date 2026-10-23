"""Compatibility entry point for the presentation application."""

from .presentation.app import AppMode, SimulationApp, build_parser, main

__all__ = ["AppMode", "SimulationApp", "build_parser", "main"]


if __name__ == "__main__":
    main()
