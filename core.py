import ast
import base64
import binascii
import html
import re
from collections import Counter
from pathlib import PurePath


def safe_filename(name: str) -> str:
    name = PurePath(name.replace("\\", "/")).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return (name or "output.txt")[:120]


def analyze_code(source: str) -> str:
    lower = source.lower()
    checks = [
        ("Hex-style escaped strings (\\xNN)", r"\\x[0-9a-fA-F]{2}"),
        ("Unicode escapes (\\uNNNN)", r"\\u[0-9a-fA-F]{4}"),
        ("Hexadecimal numeric literals", r"\b0x[0-9a-fA-F]{2,}\b"),
        ("Obfuscated variable names (_0x...)", r"\b_0x[a-fA-F0-9]+\b"),
        ("eval() calls", r"\beval\s*\("),
        ("new Function() calls", r"\bnew\s+Function\s*\("),
        ("Base64 decode calls (atob)", r"\batob\s*\("),
        ("fromCharCode calls", r"\bString\s*\.\s*fromCharCode\s*\("),
        ("Potential anti-debug code", r"debugger\s*;|console\s*\.\s*clear"),
        ("Dynamic script creation", r"createElement\s*\(\s*['\"]script"),
        ("Long encoded-looking strings", r"['\"][A-Za-z0-9+/=_-]{160,}['\"]"),
    ]
    findings = []
    for label, pattern in checks:
        count = len(re.findall(pattern, source, flags=re.I))
        if count:
            findings.append(f"• {label}: {count} occurrence(s)")

    lines = [
        "🔍 HTML/JavaScript Analysis",
        "",
        f"Characters: {len(source):,}",
        f"Lines: {source.count(chr(10)) + 1:,}",
        f"Approx. words/tokens separated by whitespace: {len(source.split()):,}",
        "",
        "Findings:",
    ]
    lines.extend(findings or ["• এই সাধারণ checks-এ পরিচিত obfuscation pattern পাওয়া যায়নি। এটি নিরাপদ বা obfuscation-মুক্ত হওয়ার প্রমাণ নয়।"])
    lines += [
        "",
        "Safety note:",
        "• এই বিশ্লেষণ static pattern matching; কোড execute করা হয়নি।",
        "• False positive/false negative হতে পারে।",
        "• Server-side logic, encryption, missing keys বা custom virtual machines শুধু pattern matching দিয়ে recover করা যায় না.",
    ]
    return "\n".join(lines)


def beautify_code(source: str) -> str:
    """Conservative formatter for HTML and JS; it does not run or evaluate code."""
    source = source.replace("\r\n", "\n").replace("\r", "\n")
    # If this looks like HTML, indent tags while preserving raw script/style contents.
    if re.search(r"<\s*(html|head|body|div|script|style|!doctype)\b", source, re.I):
        return _beautify_html(source)
    return _beautify_js(source)


def _beautify_html(source: str) -> str:
    tokens = re.split(r"(<script\b[^>]*>|</script\s*>|<style\b[^>]*>|</style\s*>|<!--.*?-->|<[^>]+>)", source, flags=re.I | re.S)
    out, depth, raw_mode = [], 0, None
    for token in tokens:
        if not token:
            continue
        stripped = token.strip()
        if not stripped:
            continue
        low = stripped.lower()
        if low.startswith("</script") or low.startswith("</style"):
            raw_mode = None
        if raw_mode:
            raw = token.strip("\n")
            if raw:
                out.append("    " * depth + raw)
            continue
        if low.startswith("</"):
            depth = max(0, depth - 1)
            out.append("    " * depth + stripped)
        elif low.startswith("<!--"):
            out.append("    " * depth + stripped)
        elif re.match(r"<(?:!doctype|!|\\?)", low):
            out.append("    " * depth + stripped)
        else:
            out.append("    " * depth + stripped)
            if re.match(r"<(script|style)\b", low):
                raw_mode = "raw"
                depth += 1
            elif re.match(r"<[a-z][^>]*[^/]>", low) and not re.match(
                r"<(area|base|br|col|embed|hr|img|input|link|meta|param|source|track|wbr)\b", low
            ):
                depth += 1
    return "\n".join(out) + "\n"


def _beautify_js(source: str) -> str:
    # Token-based lightweight formatter. Strings/comments are preserved as tokens.
    token_re = re.compile(
        r'("(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|`(?:\\.|[^`\\])*`|//[^\n]*|/\*.*?\*/|'
        r'[A-Za-z_$][\w$]*|0x[0-9a-fA-F]+|\d+(?:\.\d+)?|===|!==|=>|==|!=|<=|>=|\+\+|--|&&|\|\||\?\?|'
        r'\+=|-=|\*=|/=|[{}()\[\];,.?:]|[^\s])',
        re.S,
    )
    tokens = token_re.findall(source)
    out, indent, line, prev = [], 0, "", ""
    def flush():
        nonlocal line
        if line.strip():
            out.append("    " * indent + line.strip())
        line = ""
    for tok in tokens:
        if tok.startswith("//") or tok.startswith("/*"):
            if line.strip():
                line += " "
            line += tok
            flush()
            prev = tok
            continue
        if tok == "}":
            flush()
            indent = max(0, indent - 1)
            line = "}"
            flush()
        elif tok == "{":
            if line.strip():
                line += " "
            line += "{"
            flush()
            indent += 1
        elif tok == ";":
            line = line.rstrip() + ";"
            flush()
        elif tok == ",":
            line = line.rstrip() + ", "
        elif tok in (")", "]", ".", "?."):
            line = line.rstrip() + tok
        elif tok in ("(", "["):
            if prev and (prev.isidentifier() or prev in (")", "]", "}", "=>")):
                line = line.rstrip() + " "
            line += tok
        elif tok in (":",):
            line = line.rstrip() + ": "
        elif tok in ("=", "+", "-", "*", "/", "==", "===", "!=", "!==", "<", ">", "<=", ">=", "=>", "&&", "||", "??", "+=", "-=", "*=", "/="):
            line = line.rstrip() + f" {tok} "
        else:
            if line and not line.endswith((" ", "(", "[", ".", "?.", "!")) and tok not in ("!", "~"):
                line += " "
            line += tok
        prev = tok
    flush()
    return "\n".join(out) + "\n"


def basic_decode(source: str):
    """Decode only literal, bounded patterns; never eval/execute source."""
    notes = []
    output = source

    # Decode JS hex/unicode escapes inside quoted string literals only.
    string_re = re.compile(r"""(['"])(?:\\.|(?!\1)[^\\])*?\1""")
    def decode_escapes(match):
        s = match.group(0)
        quote, body = s[0], s[1:-1]
        changed = False
        def replace_hex(m):
            nonlocal changed
            changed = True
            return chr(int(m.group(1), 16))
        def replace_unicode(m):
            nonlocal changed
            changed = True
            return chr(int(m.group(1), 16))
        try:
            decoded = re.sub(r"\\x([0-9a-fA-F]{2})", replace_hex, body)
            decoded = re.sub(r"\\u([0-9a-fA-F]{4})", replace_unicode, decoded)
            if changed:
                notes.append("কিছু quoted string-এর \\xNN/\\uNNNN escape decode করা হয়েছে।")
            decoded = decoded.replace("\\", "\\\\").replace(quote, "\\" + quote)
            return quote + decoded + quote
        except Exception:
            return s

    output = string_re.sub(decode_escapes, output)

    # Decode literal atob("...") / atob('...') calls, bounded to 64 KiB.
    atob_re = re.compile(r"""atob\s*\(\s*(['"])([A-Za-z0-9+/=_-]{4,87384})\1\s*\)""", re.I)
    def decode_b64(match):
        try:
            value = match.group(2)
            value += "=" * ((4 - len(value) % 4) % 4)
            decoded = base64.b64decode(value, validate=False)
            if len(decoded) <= 65536:
                text = decoded.decode("utf-8")
                notes.append("কিছু literal atob('base64') string decode করা হয়েছে।")
                return repr(text)
        except (ValueError, UnicodeDecodeError, binascii.Error):
            pass
        return match.group(0)
    output, n = atob_re.subn(decode_b64, output)

    # Decode simple String.fromCharCode(65, 66, ...) calls.
    char_re = re.compile(r"String\s*\.\s*fromCharCode\s*\(\s*((?:\d{1,5}\s*,\s*){1,2047}\d{1,5})\s*\)")
    def decode_chars(match):
        try:
            nums = [int(x.strip()) for x in match.group(1).split(",")]
            if all(0 <= x <= 65535 for x in nums):
                notes.append("কিছু literal String.fromCharCode(...) sequence decode করা হয়েছে।")
                return repr("".join(chr(x) for x in nums))
        except Exception:
            pass
        return match.group(0)
    output, n2 = char_re.subn(decode_chars, output)

    if not notes:
        notes.append("নিরাপদে decode করা যায় এমন পরিচিত literal pattern পাওয়া যায়নি।")
    notes.append("গুরুত্বপূর্ণ: eval(), Function(), script বা input কোড চালানো হয়নি।")
    notes.append("Basic decoder সীমিত; সব obfuscation বা encrypted payload decode করতে পারে না।")
    return output, notes
