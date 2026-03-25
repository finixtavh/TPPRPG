from sshkeyboard import listen_keyboard, stop_listening


def wait_for_enter() -> None:
    done = {"pressed": False}
    print("Presiona Enter")
    def _on_press(key: str) -> None:
        if key == "enter":
            done["pressed"] = True
            stop_listening()

    listen_keyboard(on_press=_on_press, sequential=True)
