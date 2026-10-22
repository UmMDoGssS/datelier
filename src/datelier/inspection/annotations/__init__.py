"""Preserved detection annotations with explicit image association and overlays.

Filename, stem, resolved path, or scalar image-key mappings bind annotation
sources to file/view row IDs; ambiguous keys require explicit mappings. Header
dimensions suffice for association. Pixel-edge conversions preserve original
coordinates and report out-of-bounds geometry without clamping. Multiple-source
overlays and profiles retain class/source/confidence and exact/sampled scope.
"""
