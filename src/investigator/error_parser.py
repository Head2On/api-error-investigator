import re 
from typing import TypedDict

class ParsedError(TypedDict):
    error_type: str | None
    message: str | None
    file: str | None
    line: int | None
    function: str | None
    stack_trace: str

_FRAME_RE = re.compile(
    r'File "(?P<file>[^"]+)", line (?P<line>\d+), in (?P<function>\S+)'
)

_ERROR_LINE_RE = re.compile(
    r'^(?P<error_type>[A-Za-z_][\w\.]*(?:Error|Exception|Warning|Exit))'
    r'(?::\s*(?P<message>.*))?$'
)

def parse_error(raw_error: str) -> ParsedError:
    result: ParsedError = {
        "error_type": None,
        "message": None,
        "file": None,
        "line": None,
        "function": None,
        "stack_trace": raw_error,
    }

    lines = [ln.rstrip() for ln in raw_error.strip().splitlines()]
    if not lines:
        return result
    
    # Find the error line for bottom to up
    error_line_index = None
    for i in range(len(lines) - 1, -1, -1):
        match = _ERROR_LINE_RE.match(lines[i].strip())
        if match:
            result["error_type"] = match.group("error_type")
            result["message"] = match.group("message")
            error_line_index = i
            break

    #Find the last frame
    search_until = error_line_index if error_line_index is not None else len(lines)
    for i in range(search_until - 1, -1, -1):
        frame = _FRAME_RE.search(lines[i])
        if frame:
            result["file"] = frame.group("file")
            result["line"] = int(frame.group("line"))
            result["function"] = frame.group("function")
            break

    return result