import streamlit as st
import io
import contextlib
import traceback
import multiprocessing
import time
import json
import os
import re
from streamlit_ace import st_ace

st.set_page_config(
    page_title="Python Online Compiler",
    layout="wide",
    initial_sidebar_state="expanded"
)

HISTORY_FILE = "history.json"

# ----------------------------
# HISTORY FILE FUNCTIONS
# ----------------------------
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []


def save_history(history):
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=4)
    except Exception:
        pass


# ----------------------------
# CUSTOM CSS
# ----------------------------
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1rem;
        padding-left: 2rem;
        padding-right: 2rem;
        max-width: 100%;
    }

    h1 {
        font-size: 30px !important;
    }

    h2, h3 {
        font-size: 18px !important;
    }

    html, body, [class*="css"] {
        font-family: "Source Sans Pro", sans-serif;
        font-size: 14px !important;
    }

    .ace_editor, .ace_text-input, .ace_content {
        font-family: "Consolas", monospace !important;
        font-size: 15px !important;
        line-height: 1.4 !important;
    }

    .stButton button {
        height: 38px;
        font-size: 14px;
    }

    pre {
        font-size: 14px !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# TITLE
# ----------------------------
st.markdown(
    """
    <h1 style='text-align: center; margin-bottom: 0px;'>
        🧠 Python Online Compiler
    </h1>
    """,
    unsafe_allow_html=True
)

st.markdown(
    """
    <p style='text-align: center; color: gray; margin-top: 0px; margin-bottom: 15px;'>
        Secure browser-based Python IDE
    </p>
    """,
    unsafe_allow_html=True
)

# ----------------------------
# THEME
# ----------------------------
theme = st.get_option("theme.base")

if theme == "dark":
    ace_theme = "monokai"
else:
    ace_theme = "github"

# ----------------------------
# SESSION STATE
# ----------------------------
if "history" not in st.session_state:
    st.session_state.history = load_history()

if "last_error_line" not in st.session_state:
    st.session_state.last_error_line = None

if "last_code" not in st.session_state:
    st.session_state.last_code = "Write your Python code here..."


# ----------------------------
# SAFE EXECUTION FUNCTION
# ----------------------------
def run_code(code, q):
    stdout = io.StringIO()
    stderr = io.StringIO()

    allowed_builtins = {
        "print": print,
        "range": range,
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "list": list,
        "dict": dict,
        "set": set,
        "tuple": tuple,
        "bool": bool,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "map": map,
        "round": round,
        "enumerate": enumerate,
        "filter": filter,
        "zip": zip,
        "sorted": sorted,
        "any": any,
        "all": all,
        "reversed": reversed,

        # Exception classes
        "Exception": Exception,
        "BaseException": BaseException,
        "ZeroDivisionError": ZeroDivisionError,
        "ValueError": ValueError,
        "TypeError": TypeError,
        "IndexError": IndexError,
        "KeyError": KeyError,
        "NameError": NameError,
        "SyntaxError": SyntaxError,
        "ImportError": ImportError,
        "AttributeError": AttributeError,
        "RuntimeError": RuntimeError,
        "RecursionError": RecursionError,
    }

    safe_globals = {
        "__builtins__": allowed_builtins
    }

    try:
        compiled = compile(code, "user_code", "exec")

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exec(compiled, safe_globals)

        q.put((stdout.getvalue(), stderr.getvalue(), None))

    except Exception as e:
        error_message = f"{type(e).__name__}: {e}"
        q.put(("", error_message, traceback.format_exc()))


# ----------------------------
# ERROR LINE FINDER
# ----------------------------
def get_error_line(trace):
    if not trace:
        return None

    matches = re.findall(r'File "user_code", line (\d+)', trace)

    if matches:
        return int(matches[-1])

    return None


# ----------------------------
# EDITOR ERROR ANNOTATION
# ----------------------------
error_annotations = []

if st.session_state.last_error_line:
    error_annotations = [
        {
            "row": st.session_state.last_error_line - 1,
            "column": 0,
            "text": f"Error on line {st.session_state.last_error_line}",
            "type": "error"
        }
    ]


# ----------------------------
# LAYOUT
# ----------------------------
col1, col2 = st.columns([1.1, 1])

with col1:
    st.subheader("📝 Editor")

    code = st_ace(
        value=st.session_state.last_code,
        placeholder="Write Python code here...",
        language="python",
        theme=ace_theme,
        height=420,
        keybinding="vscode",
        font_size=15,
        tab_size=4,
        show_gutter=True,
        show_print_margin=False,
        wrap=True,
        auto_update=True,
        annotations=error_annotations,
        key="code_editor"
    )

    col_run, col_download = st.columns(2)

    with col_run:
        run = st.button("▶ Run Code", use_container_width=True)

    with col_download:
        st.download_button(
            "⬇ Download .py",
            data=code or "",
            file_name="script.py",
            mime="text/plain",
            use_container_width=True
        )

    if run:
        if not code or code.strip() == "":
            st.warning("Please write some Python code first.")
        else:
            st.session_state.last_code = code
            st.session_state.last_error_line = None

            q = multiprocessing.Queue()

            with st.spinner("Running code..."):
                p = multiprocessing.Process(target=run_code, args=(code, q))
                p.start()
                p.join(3)

            if p.is_alive():
                p.terminate()
                p.join()

                new_item = {
                    "code": code,
                    "output": "",
                    "error": "⛔ Timeout: Code took too long",
                    "trace": None,
                    "error_line": None,
                    "time": time.strftime("%d-%m-%Y %H:%M:%S")
                }

                st.session_state.history.append(new_item)
                save_history(st.session_state.history)

                st.error("⛔ Timeout: Code took too long")

            else:
                if not q.empty():
                    out, err, trace = q.get()
                else:
                    out, err, trace = "", "No output returned", None

                error_line = get_error_line(trace)
                st.session_state.last_error_line = error_line

                new_item = {
                    "code": code,
                    "output": out,
                    "error": err,
                    "trace": trace,
                    "error_line": error_line,
                    "time": time.strftime("%d-%m-%Y %H:%M:%S")
                }

                st.session_state.history.append(new_item)
                save_history(st.session_state.history)

                st.success("Execution complete")

                if error_line:
                    st.warning(f"Error found on line {error_line}. Refresh/rerun will highlight it in editor.")


# ----------------------------
# OUTPUT PANEL
# ----------------------------
with col2:
    st.subheader("📟 Output")

    if st.session_state.history:
        last = st.session_state.history[-1]

        st.caption(f"Last Run Time: {last['time']}")

        if last.get("error_line"):
            st.warning(f"Error Line: {last['error_line']}")

        if last["output"]:
            st.markdown("### ✅ Output")
            st.code(last["output"], language="text")

        if last["error"]:
            st.markdown("### ❌ Error")
            st.error(last["error"])

        if last["trace"]:
            st.markdown("### 🔍 Traceback")
            st.code(last["trace"], language="python")

        if not last["output"] and not last["error"] and not last["trace"]:
            st.info("Code executed successfully, but no output was printed.")

    else:
        st.info("Run your code to see output here.")


# ----------------------------
# SIDEBAR HISTORY
# ----------------------------
st.sidebar.title("📜 History")

if st.sidebar.button("🗑️ Clear History"):
    st.session_state.history = []
    save_history([])
    st.sidebar.success("History cleared")

for item in reversed(st.session_state.history[-20:]):
    title = f"⏰ {item['time']}"

    if item.get("error_line"):
        title += f" | Error Line {item['error_line']}"

    with st.sidebar.expander(title):
        st.code(item["code"], language="python")

        if item["output"]:
            st.markdown("✅ Output")
            st.text(item["output"])

        if item["error"]:
            st.markdown("❌ Error")
            st.error(item["error"])

        if item.get("error_line"):
            st.markdown(f"🔴 Error Line: `{item['error_line']}`")


# ----------------------------
# FOOTER
# ----------------------------
st.markdown("---")
st.markdown(
    """
    <p style='text-align: center; color: gray; font-size: 13px;'>
        ⚠ For interview and learning purposes only — not intended for production use
    </p>
    """,
    unsafe_allow_html=True
)