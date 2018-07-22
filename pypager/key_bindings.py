from __future__ import unicode_literals
from prompt_toolkit.application import get_app
from prompt_toolkit.filters import has_focus, Condition
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_up, scroll_page_down, scroll_one_line_down, scroll_one_line_up, scroll_half_page_up, scroll_half_page_down
from prompt_toolkit.keys import Keys
from prompt_toolkit.search import stop_search
from prompt_toolkit.utils import suspend_to_background_supported


__all__ = (
    'create_key_bindings',
)

def create_key_bindings(pager):
    kb = KeyBindings()
    handle = kb.add

    @Condition
    def has_colon():
        return pager.in_colon_mode

    @Condition
    def default_focus():
        app = get_app()
        return app.layout.current_window == pager.current_source_info.window

    @Condition
    def displaying_help():
       return pager.displaying_help

    for c in '01234556789':
        @handle(c, filter=default_focus)
        def _(event, c=c):
            event.append_to_arg_count(c)

    @handle('q', filter=default_focus)
    @handle('Q', filter=default_focus | has_colon)
    @handle('Z', 'Z', filter=default_focus)
    def _(event):
        " Quit. "
        if pager.displaying_help:
            pager.quit_help()
        else:
            event.app.exit()

    @handle(' ', filter=default_focus)
    @handle('f', filter=default_focus)
    @handle(Keys.ControlF, filter=default_focus)
    @handle(Keys.ControlV, filter=default_focus)
    def _(event):
        " Page down."
        scroll_page_down(event)

    @handle('b', filter=default_focus)
    @handle(Keys.ControlB, filter=default_focus)
    @handle(Keys.Escape, 'v', filter=default_focus)
    def _(event):
        " Page up."
        scroll_page_up(event)

    @handle('d', filter=default_focus)
    @handle(Keys.ControlD, filter=default_focus)
    def _(event):
        " Half page down."
        scroll_half_page_down(event)

    @handle('u', filter=default_focus)
    @handle(Keys.ControlU, filter=default_focus)
    def _(event):
        " Half page up."
        scroll_half_page_up(event)

    @handle('e', filter=default_focus)
    @handle('j', filter=default_focus)
    @handle(Keys.ControlE, filter=default_focus)
    @handle(Keys.ControlN, filter=default_focus)
    @handle(Keys.ControlJ, filter=default_focus)
    @handle(Keys.ControlM, filter=default_focus)
    @handle(Keys.Down, filter=default_focus)
    def _(event):
        " Scoll one line down."
        if event.arg > 1:
            # When an argument is given, go this amount of lines down.
            event.current_buffer.auto_down(count=event.arg)
        else:
            scroll_one_line_down(event)

    @handle('y', filter=default_focus)
    @handle('k', filter=default_focus)
    @handle(Keys.ControlY, filter=default_focus)
    @handle(Keys.ControlK, filter=default_focus)
    @handle(Keys.ControlP, filter=default_focus)
    @handle(Keys.Up, filter=default_focus)
    def _(event):
        " Scoll one line up."
        if event.arg > 1:
            event.current_buffer.auto_up(count=event.arg)
        else:
            scroll_one_line_up(event)

    @handle(Keys.Escape, 'u')
    def _(event):
        " Toggle search highlighting. "
        pager.highlight_search = not pager.highlight_search

    @handle('=', filter=default_focus)
    @handle(Keys.ControlG, filter=default_focus)
    @handle('f', filter=has_colon)
    def _(event):
        " Print the current file name. "
        pager.message = ' {} '.format(pager.current_source.get_name())

    @handle('h', filter=default_focus & ~displaying_help)
    @handle('H', filter=default_focus & ~displaying_help)
    def _(event):
        " Display Help. "
        pager.display_help()

    @handle('g', filter=default_focus)
    @handle('<', filter=default_focus)
    @handle(Keys.Escape, '<', filter=default_focus)
    def _(event):
        " Go to the first line of the file. "
        event.current_buffer.cursor_position = 0

    @handle('G', filter=default_focus)
    @handle('>', filter=default_focus)
    @handle(Keys.Escape, '>', filter=default_focus)
    def _(event):
        " Go to the last line of the file. "
        b = event.current_buffer
        b.cursor_position = len(b.text)

    @handle('m', Keys.Any, filter=default_focus)
    def _(event):
        " Mark current position. "
        source_info = pager.current_source_info

        source_info.marks[event.data] = (
            event.current_buffer.cursor_position,
            source_info.window.vertical_scroll)

    @handle("'", Keys.Any, filter=default_focus)
    def _(event):
        " Go to a previously marked position. "
        go_to_mark(event, event.data)

    @handle(Keys.ControlX, Keys.ControlX, filter=default_focus)
    def _(event):
        " Same as '. "
        go_to_mark(event, '.')

    def go_to_mark(event, mark):
        b = event.current_buffer
        source_info = pager.current_source_info
        try:
            if mark == '^':  # Start of file.
                cursor_pos, vertical_scroll = 0, 0
            elif mark == '$':  # End of file - mark.
                cursor_pos, vertical_scroll = len(b.text), 0
            else:  # Custom mark.
                cursor_pos, vertical_scroll = source_info.marks[mark]
        except KeyError:
            pass  # TODO: show warning.
        else:
            b.cursor_position = cursor_pos
            source_info.window.vertical_scroll = vertical_scroll

    @handle('F', filter=default_focus)
    def _(event):
        " Forward forever, like 'tail -f'. "
        pager.forward_forever = True

    @handle('r', filter=default_focus)
    @handle('R', filter=default_focus)
    def _(event):
        event.app.renderer.clear()

    def search_buffer_is_empty():
        " Returns True when the search buffer is empty. "
        return pager.search_buffer.text == ''

    @handle('backspace', filter=has_focus(pager.search_buffer) & Condition(search_buffer_is_empty))
    def _(event):
        " Cancel search when backspace is pressed. "
        stop_search()

    @handle(Keys.Left, filter=default_focus)
    @handle(Keys.Escape, '(', filter=default_focus)
    def _(event):
        " Scroll half page to the left. "
        w = event.app.layout.current_window
        b = event.app.current_buffer

        if w and w.render_info:
            info = w.render_info
            amount = info.window_width // 2

            # Move cursor horizontally.
            value = b.cursor_position - min(amount, len(b.document.current_line_before_cursor))
            b.cursor_position = value

            # Scroll.
            w.horizontal_scroll = max(0, w.horizontal_scroll - amount)

    @handle(Keys.Right, filter=default_focus)
    @handle(Keys.Escape, ')', filter=default_focus)
    def _(event):
        " Scroll half page to the right. "
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
                    b.cursor_position = b.document.translate_row_col_to_index(line, xpos)
                    break

            # Scroll.
            w.horizontal_scroll = max(0, w.horizontal_scroll + amount)

    @handle(':', filter=default_focus & ~displaying_help)
    def _(event):
        pager.in_colon_mode = True

    @handle('n', filter=has_colon)
    def _(event):
        " Go to next file. "
        pager.focus_next_source()

    @handle('p', filter=has_colon)
    def _(event):
        " Go to previous file. "
        pager.focus_previous_source()

    @handle('e', filter=has_colon)
    @handle(Keys.ControlX, Keys.ControlV, filter=default_focus)
    def _(event):
        event.app.layout.focus(pager.layout.examine_control)
        pager.in_colon_mode = False

    @handle('d', filter=has_colon)
    def _(event):
        pager.remove_current_source()

    @handle('backspace', filter=has_colon)
    @handle('q', filter=has_colon)
    def _(event):
        pager.in_colon_mode = False

    @handle(Keys.Any, filter=has_colon)
    def _(event):
        pager.in_colon_mode = False
        pager.message = 'No command.'

    @handle(Keys.ControlC, filter=has_focus('EXAMINE'))
    @handle(Keys.ControlG, filter=has_focus('EXAMINE'))
    def _(event):
        " Cancel 'Examine' input. "
        event.app.layout.focus(pager.current_source_info.window)

    @handle(Keys.ControlZ, filter=Condition(lambda: suspend_to_background_supported()))
    def _(event):
        " Suspend to bakground. "
        event.app.suspend_to_background()

    return kb
