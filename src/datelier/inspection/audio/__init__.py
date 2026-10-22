"""Header-first file/mapped-array audio inspection in original signal units.

Original rate, dtype, channel layout, amplitude units, and selected frame ranges
travel with statistics, waveform extrema, PSD/HTK mel views, and comparisons.
Array audio needs an explicit rate for time/frequency views and playback.
Display transforms never resample or replace source samples. Collection scans
and playback require explicit commands; loading/restoring remain silent.
"""
