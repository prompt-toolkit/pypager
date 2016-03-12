from __future__ import unicode_literals
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_up, scroll_page_down, scroll_one_line_down, scroll_one_line_up, scroll_half_page_up, scroll_half_page_down
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.filters import HasFocus, Condition
from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER, IncrementalSearchDirection
from prompt_toolkit.keys import Keys
from prompt_toolkit.key_binding.vi_state import InputMode
from prompt_toolkit.utils import suspend_to_background_supported

__all__ = (
    'create_key_bindings',
)

def create_key_bindings(pager):
    manager = KeyBindingManager(
        enable_vi_mode=False,
        enable_search=True,
        enable_extra_page_navigation=True,
        enable_system_bindings=False)
    handle = manager.registry.add_binding

    default_focus = HasFocus(DEFAULT_BUFFER)

    for c in '01234556789':
        @handle(c, filter=default_focus)
        def _(event, c=c):
            event.append_to_arg_count(c)

    @handle('q', filter=default_focus)
    @handle('Q', filter=default_focus)
    @handle('Z', 'Z', filter=default_focus)
    def _(event):
        " Quit. "
        event.cli.set_return_value(None)

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
        scroll_one_line_down(event)

    @handle('y', filter=default_focus)
    @handle('k', filter=default_focus)
    @handle(Keys.ControlY, filter=default_focus)
    @handle(Keys.ControlK, filter=default_focus)
    @handle(Keys.ControlP, filter=default_focus)
    @handle(Keys.Up, filter=default_focus)
    def _(event):
        " Scoll one line up."
        scroll_one_line_up(event)

    @handle('/', filter=default_focus)
    def _(event):
        " Start searching forward. "
        event.cli.search_state.direction = IncrementalSearchDirection.FORWARD
        # get_vi_state(event.cli).input_mode = InputMode.INSERT
        event.cli.push_focus(SEARCH_BUFFER)

    @handle('?', filter=default_focus)
    def _(event):
        " Start searching backwards. "
        event.cli.search_state.direction = IncrementalSearchDirection.BACKWARD
        # get_vi_state(event.cli).input_mode = InputMode.INSERT
        event.cli.push_focus(SEARCH_BUFFER)

    @handle('n', filter=default_focus)
    def _(event):
        " Search next. "
        event.current_buffer.apply_search(
            event.cli.search_state, include_current_position=False,
            count=event.arg)

    @handle('N', filter=default_focus)
    def _(event):
        " Search previous. "
        event.current_buffer.apply_search(
            ~event.cli.search_state, include_current_position=False,
            count=event.arg)

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
        pager.marks[event.data] = (
            event.current_buffer.cursor_position,
            pager.layout.buffer_window.vertical_scroll)

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
        try:
            if mark == '^':  # Start of file.
                cursor_pos, vertical_scroll = 0, 0
            elif mark == '$':  # End of file - mark.
                cursor_pos, vertical_scroll = len(b.text), 0
            else:  # Custom mark.
                cursor_pos, vertical_scroll = pager.marks[mark]
        except KeyError:
            pass  # TODO: show warning.
        else:
            b.cursor_position = cursor_pos
            pager.layout.buffer_window.vertical_scroll = vertical_scroll

    @handle('F', filter=default_focus)
    def _(event):
        " Forward forever, like 'tail -f'. "
        pager.forward_forever = True

    def search_buffer_is_empty(cli):
        " Returns True when the search buffer is empty. "
        return cli.buffers[SEARCH_BUFFER].text == ''

    @handle(Keys.Backspace, filter=HasFocus(SEARCH_BUFFER) & Condition(search_buffer_is_empty))
    def _(event):
        " Cancel search when backspace is pressed. "
        # get_vi_state(event.cli).input_mode = InputMode.NAVIGATION
        event.cli.pop_focus()
        event.cli.buffers[SEARCH_BUFFER].reset()

    @handle(Keys.ControlZ, filter=Condition(lambda cli: suspend_to_background_supported()))
    def _(event):
        " Suspend to bakground. "
        event.cli.suspend_to_background()

    return manager
