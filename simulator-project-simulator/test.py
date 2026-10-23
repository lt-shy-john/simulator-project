from prompt_toolkit import prompt
from prompt_toolkit.lexers import PygmentsLexer
from pygments.lexers.python import PythonLexer
from prompt_toolkit.enums import EditingMode

from simpleeval import simple_eval

print(simple_eval("'a' if 1 > 0 else 'b'"))


def get_setting_input(current_value: str) -> str:
    """Prompt the user to edit a setting value using vi-style keybindings.

    Args:
        current_value: The existing value to pre-fill for editing.

    Returns:
        The new value entered by the user.
    """
    return prompt(
        "edit setting> \n",
        lexer=PygmentsLexer(PythonLexer),
        default=current_value,
        vi_mode=True,
        multiline=True,
        bottom_toolbar=" [i] insert  [Esc] normal mode  [Alt+Enter]/[Esc then Enter] submit  [Ctrl+C] cancel ",
    )

result = get_setting_input('txt = "hello_world"\nif type(txt) == str: \n    print(":)")')
print("\n================== Result ==================")
print(result)