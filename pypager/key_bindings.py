from typing import TYPE_CHECKING

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition, has_focus
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import (
    scroll_half_page_down,
    scroll_half_page_up,
    scroll_one_line_down,
    scroll_one_line_up,
    scroll_page_down,
    scroll_page_up,
)
from prompt_toolkit.key_binding.key_processor import KeyPressEvent
from prompt_toolkit.keys import Keys
from prompt_toolkit.search import stop_search
from prompt_toolkit.utils import suspend_to_background_supported

if TYPE_CHECKING:
    from .pager import Pager


__all__ = [
    "create_key_bindings",
]

E = KeyPressEvent


def create_key_bindings(pager: "Pager") -> KeyBindings:
    kb = KeyBindings()
    handle = kb.add

    @Condition
    def has_colon() -> bool:
        return pager.in_colon_mode

    @Condition
    def default_focus() -> bool:
        app = get_app()
        return app.layout.current_window == pager.current_source_info.window

    @Condition
    def displaying_help() -> bool:
        return pager.displaying_help

    for c in "01234556789":

        @handle(c, filter=default_focus)
        def _handle_arg(event: E, c: str = c) -> None:
            event.append_to_arg_count(c)

    @handle("q", filter=default_focus, eager=True)
    # Eager because q-any is a registered Vi key binding.
    @handle("Q", filter=default_focus | has_colon)
    @handle("Z", "Z", filter=default_focus)
    def _quit(event: E) -> None:
        "Quit."
        if pager.displaying_help:
            pager.quit_help()
        else:
            event.app.exit()

    @handle(" ", filter=default_focus)
    @handle("f", filter=default_focus)
    @handle("c-f", filter=default_focus)
    @handle("c-v", filter=default_focus)
    def _pagedown(event: E) -> None:
        "Page down."
        scroll_page_down(event)

    @handle("b", filter=default_focus)
    @handle("c-b", filter=default_focus)
    @handle("escape", "v", filter=default_focus)
    def _pageup(event: E) -> None:
        "Page up."
        scroll_page_up(event)

    @handle("d", filter=default_focus)
    @handle("c-d", filter=default_focus)
    def _halfdown(event: E) -> None:
        "Half page down."
        scroll_half_page_down(event)

    @handle("u", filter=default_focus)
    @handle("c-u", filter=default_focus)
    def _halfup(event: E) -> None:
        "Half page up."
        scroll_half_page_up(event)

    @handle("e", filter=default_focus)
    @handle("j", filter=default_focus)
    @handle("c-e", filter=default_focus)
    @handle("c-n", filter=default_focus)
    @handle("c-j", filter=default_focus)
    @handle("c-m", filter=default_focus)
    @handle("down", filter=default_focus)
    def _down(event: E) -> None:
        "Scoll one line down."
        if event.arg > 1:
            # When an argument is given, go this amount of lines down.
            event.current_buffer.auto_down(count=event.arg)
        else:
            scroll_one_line_down(event)

    @handle("y", filter=default_focus)
    @handle("k", filter=default_focus)
    @handle("c-y", filter=default_focus)
    @handle("c-k", filter=default_focus)
    @handle("c-p", filter=default_focus)
    @handle("up", filter=default_focus)
    def _up(event: E) -> None:
        "Scoll one line up."
        if event.arg > 1:
            event.current_buffer.auto_up(count=event.arg)
        else:
            scroll_one_line_up(event)

    @handle(Keys.Escape, "u")
    def _toggle_highlighting(event: E) -> None:
        "Toggle search highlighting."
        pager.highlight_search = not pager.highlight_search

    @handle("=", filter=default_focus)
    @handle(Keys.ControlG, filter=default_focus)
    @handle("f", filter=has_colon)
    def _print_filename(event: E) -> None:
        "Print the current file name."
        pager.message = " {} ".format(pager.current_source.get_name())

    @handle("h", filter=default_focus & ~displaying_help)
    @handle("H", filter=default_focus & ~displaying_help)
    def _help(event: E) -> None:
        "Display Help."
        pager.display_help()

    @handle("g", filter=default_focus)
    @handle("<", filter=default_focus)
    @handle("escape", "<", filter=default_focus)
    def _firstline(event: E) -> None:
        "Go to the first line of the file."
        event.current_buffer.cursor_position = 0

    @handle("G", filter=default_focus)
    @handle(">", filter=default_focus)
    @handle("escape", ">", filter=default_focus)
    def _lastline(event: E) -> None:
        "Go to the last line of the file."
        b = event.current_buffer
        b.cursor_position = len(b.text)

    @handle("m", Keys.Any, filter=default_focus)
    def _mark(event: E) -> None:
        "Mark current position."
        source_info = pager.current_source_info

        source_info.marks[event.data] = (
            event.current_buffer.cursor_position,
            source_info.window.vertical_scroll,
        )

    @handle("'", Keys.Any, filter=default_focus)
    def _goto_mark(event: E) -> None:
        "Go to a previously marked position."
        go_to_mark(event, event.data)

    @handle("c-x", Keys.ControlX, filter=default_focus)
    def _gotomark_dot(event: E) -> None:
        "Same as '."
        go_to_mark(event, ".")

    def go_to_mark(event: E, mark: str) -> None:
        b = event.current_buffer
        source_info = pager.current_source_info
        try:
            if mark == "^":  # Start of file.
                cursor_pos, vertical_scroll = 0, 0
            elif mark == "$":  # End of file - mark.
                cursor_pos, vertical_scroll = len(b.text), 0
            else:  # Custom mark.
                cursor_pos, vertical_scroll = source_info.marks[mark]
        except KeyError:
            pass  # TODO: show warning.
        else:
            b.cursor_position = cursor_pos
            source_info.window.vertical_scroll = vertical_scroll

    @handle("F", filter=default_focus)
    def _follow(event: E) -> None:
        "Forward forever, like 'tail -f'."
        pager.forward_forever = True

    @handle("r", filter=default_focus)
    @handle("R", filter=default_focus)
    def _repaint(event: E) -> None:
        event.app.renderer.clear()

    @Condition
    def search_buffer_is_empty() -> bool:
        "Returns True when the search buffer is empty."
        return pager.search_buffer.text == ""

    @handle(
        "backspace",
        filter=has_focus(pager.search_buffer) & search_buffer_is_empty,
    )
    def _cancel_search(event: E) -> None:
        "Cancel search when backspace is pressed."
        stop_search()

    @Condition
    def line_wrapping_enable() -> bool:
        return pager.current_source_info.wrap_lines

    @handle("left", filter=default_focus & ~line_wrapping_enable)
    @handle("escape", "(", filter=default_focus & ~line_wrapping_enable)
    def _left(event: E) -> None:
        "Scroll half page to the left."
        w = event.app.layout.current_window
        b = event.app.current_buffer

        if w and w.render_info:
            info = w.render_info
            amount = info.window_width // 2

            # Move cursor horizontally.
            value = b.cursor_position - min(
                amount, len(b.document.current_line_before_cursor)
            )
            b.cursor_position = value

            # Scroll.
            w.horizontal_scroll = max(0, w.horizontal_scroll - amount)

    @handle("right", filter=default_focus & ~line_wrapping_enable)
    @handle("escape", ")", filter=default_focus & ~line_wrapping_enable)
    def _right(event: E) -> None:
        "Scroll half page to the right."
        w = event.app.layout.current_window
        b = event.app.current_buffer

        if w and w.render_info:
            info = w.render_info
            amount = info.window_width // 2

            # Move the cursor first to a visible line that is long enough to
            # have the cursor visible after scrolling. (Otherwise, the Window
            # will scroll back.)
            xpos = w.horizontal_scroll + amount

            for line in info.displayed_lines:
                if len(b.document.lines[line]) >= xpos:
                    b.cursor_position = b.document.translate_row_col_to_index(
                        line, xpos
                    )
                    break

            # Scroll.
            w.horizontal_scroll = max(0, w.horizontal_scroll + amount)

    @handle(":", filter=default_focus & ~displaying_help)
    def _colon(event: E) -> None:
        pager.in_colon_mode = True

    @handle("n", filter=has_colon)
    def _next_file(event: E) -> None:
        "Go to next file."
        pager.focus_next_source()

    @handle("p", filter=has_colon)
    def _previous_file(event: E) -> None:
        "Go to previous file."
        pager.focus_previous_source()

    @handle("e", filter=has_colon)
    @handle(Keys.ControlX, Keys.ControlV, filter=default_focus)
    def _examine(event: E) -> None:
        event.app.layout.focus(pager.layout.examine_control)
        pager.in_colon_mode = False

    @handle("d", filter=has_colon)
    def _remove_source(event: E) -> None:
        pager.remove_current_source()

    @handle("backspace", filter=has_colon)
    @handle("q", filter=has_colon, eager=True)
    def _cancel_colon(event: E) -> None:
        pager.in_colon_mode = False

    @handle(Keys.Any, filter=has_colon)
    def _any(event: E) -> None:
        pager.in_colon_mode = False
        pager.message = "No command."

    @handle("c-c", filter=has_focus("EXAMINE"))
    @handle("c-g", filter=has_focus("EXAMINE"))
    def _cancel_examine(event: E) -> None:
        "Cancel 'Examine' input."
        event.app.layout.focus(pager.current_source_info.window)

    @handle("c-z", filter=Condition(lambda: suspend_to_background_supported()))
    def _suspend(event: E) -> None:
        "Suspend to background."
        event.app.suspend_to_background()

    @handle("w")
    def _line_wrapping(event: E) -> None:
        "Enable/disable line wrapping."
        source_info = pager.current_source_info
        source_info.wrap_lines = not source_info.wrap_lines

    return kb
