"""Lazy local reference previews with one file-owned GUI texture cache.

Worker-prepared resolutions/CPU previews feed native uploads; retention budgets
are separate and explicit. Missing/ambiguous references show diagnostics and
choices while original cell strings remain unchanged. Shared gallery/table
consumers reuse the same owner, which releases textures when its file closes.
"""
