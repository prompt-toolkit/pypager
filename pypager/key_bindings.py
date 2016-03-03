from __future__ import unicode_literals
from prompt_toolkit.key_binding.bindings.scroll import scroll_page_down
from prompt_toolkit.key_binding.manager import KeyBindingManager
from prompt_toolkit.filters import HasFocus
from prompt_toolkit.enums import DEFAULT_BUFFER, SEARCH_BUFFER, IncrementalSearchDirection

__all__ = (
    'create_key_bindings',
)

# Key bindings.
manager = KeyBindingManager(
    enable_vi_mode=False,
    enable_search=True,
    enable_extra_page_navigation=True,
    enable_system_bindings=False)
handle = manager.registry.add_binding

default_focus = HasFocus(DEFAULT_BUFFER)

@handle('q', filter=default_focus)
@handle('Q', filter=default_focus)
@handle('Z', 'Z', filter=default_focus)
def _(event):
    " Quit. "
    event.cli.set_return_value(None)


@handle(' ', filter=default_focus)
def _(event):
    " Page down."
    scroll_page_down(event)


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

def create_key_bindings():
    return manager
