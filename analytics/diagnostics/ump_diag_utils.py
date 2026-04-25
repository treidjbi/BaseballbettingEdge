"""Shared helpers for umpire diagnostics."""


def unpack_fetch_umpires_result(result_or_tuple):
    """Support both legacy dict returns and current (result, diagnostics).

    The diagnostic script predates the A7-style tuple return shape used by
    ``fetch_umpires``. Keep it tolerant so older ad hoc calls and newer
    tuple-based callers both work.
    """
    if isinstance(result_or_tuple, tuple) and len(result_or_tuple) == 2:
        result, diagnostics = result_or_tuple
        return result, diagnostics
    return result_or_tuple, {}
