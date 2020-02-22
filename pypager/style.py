__all__ = [
    "ui_style",
]


ui_style = {
    # Standout is caused by man pages that insert a x\b in the output.
    "standout": "bold #44aaff",
    "standout2": "underline #aa8844",
    # Show current search term. (The cursor is not visible).
    "search": "bg:default fg:default reverse",
    "search.current": "bg:#aaff00 #000000 noreverse",
    # UI style
    "statusbar": "reverse",
    "statusbar cursor-position": "noreverse #ffffff bg:#884400",
    "statusbar key": "bold",
    "arg": "reverse #ccaa00",
    "search-toolbar": "bg:#333333 #ffffff",
    "search-toolbar text": "#ffffff",
    "system-toolbar": "bg:#333333 #ffffff",
    "system-toolbar text": "#ffffff",
    "examine": "bg:#333333 #ffffff",
    "examine-text": "bg:#aa88ff #000000",
    "titlebar": "bg:#333333 #ffffff",
    # Messages
    "message": "bg:#bbee88 #222222",
    "loading": "#888888",
    # Help
    "title": "bold #44aaff",
    "subtitle": "bold #8800ff",
    "line": "#888888",
    "keys": "#44aaff",
    "version": "#8800ff",
}
