"""Application coordination independent of native rendering.

Editor/file controllers own lifetime, navigation, and revision-aware publication;
feature controllers expose narrow prepared state and commands. Domain engines
perform import, transformation, statistics, and persistence in workers. GUI
composition wires these interfaces explicitly instead of passing whole sessions
to leaf widgets. Completion updates prepared state without stealing focus.
"""
