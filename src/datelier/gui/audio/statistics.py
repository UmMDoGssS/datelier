"""Render exact signal summaries without reading or profiling the source."""

from imgui_bundle import imgui

from datelier.inspection.audio.profile_types import AudioSignalProfile


def show_statistics(profile: AudioSignalProfile) -> None:
    longest = profile.longest_silence_frames / profile.metadata.require_rate()
    imgui.text_wrapped(
        f"Exact profile: frames {profile.range.start:,}–{profile.range.stop:,} "
        f"(end exclusive); {profile.duration:.6g} s; {profile.metadata.units}."
    )
    imgui.text_wrapped(
        f"All-channel silence: {profile.silence_duration:.6g} s; "
        f"longest run {longest:.6g} s; "
        f"{profile.nonfinite_frames:,} frames with nonfinite samples."
    )
    imgui.text_wrapped(
        f"Clipping rails {profile.clipping_bounds[0]} / {profile.clipping_bounds[1]}; "
        f"silence ≤ {profile.thresholds.silence:g} absolute amplitude. "
        "Percentages use finite samples."
    )
    if imgui.begin_table(
        "Signal channel statistics",
        8,
        imgui.TableFlags_.scroll_x
        | imgui.TableFlags_.scroll_y
        | imgui.TableFlags_.borders
        | imgui.TableFlags_.row_bg,
        (0, 110),
    ):
        for name in (
            "Channel",
            "Minimum",
            "Maximum",
            "Mean",
            "RMS",
            "Clipping",
            "Silence",
            "Finite / total",
        ):
            imgui.table_setup_column(name)
        imgui.table_headers_row()
        clipper = imgui.ListClipper()
        clipper.begin(len(profile.channels))
        while clipper.step():
            for index in range(clipper.display_start, clipper.display_end):
                channel = profile.channels[index]
                denominator = channel.finite or 1
                values = (
                    str(channel.channel + 1),
                    channel.minimum or "—",
                    channel.maximum or "—",
                    f"{channel.mean:.6g}" if channel.mean is not None else "—",
                    f"{channel.rms:.6g}" if channel.rms is not None else "—",
                    f"{channel.clipped:,} ({channel.clipped / denominator * 100:.3g}%)",
                    f"{channel.silent:,} ({channel.silent / denominator * 100:.3g}%)",
                    f"{channel.finite:,} / {channel.samples:,}",
                )
                imgui.table_next_row()
                for value in values:
                    imgui.table_next_column()
                    imgui.text_unformatted(value)
                if channel.diagnostic and imgui.is_item_hovered():
                    imgui.set_tooltip(channel.diagnostic)
        imgui.end_table()
