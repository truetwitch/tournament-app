
import streamlit as st
import streamlit.components.v1 as components
import random
import math
import json
import unicodedata

st.title("Dynamic Tournament Generator 🎲")

# =========================================================
# Clipboard button (safe, robust, no downloads)
# =========================================================
def clipboard_button(text_to_copy: str, label: str = "📋 Copy Fixtures"):
    """
    Renders a real 'Copy to Clipboard' button using a Streamlit component.
    Uses JSON to safely escape any characters for JS.
    """
    safe_text_js = json.dumps(text_to_copy)  # safe JS string literal

    html_code = f"""
        <div>
            <button id="copyBtn" style="
                padding: 10px 14px;
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                margin-top: 6px;
            ">{label}</button>
            <span id="copyMsg" style="margin-left:10px;color:#1b5e20;font-weight:600;"></span>
        </div>
        <script>
            const btn = document.currentScript.previousElementSibling.querySelector('#copyBtn');
            const msg = document.currentScript.previousElementSibling.querySelector('#copyMsg');
            btn.addEventListener('click', async () => {{
                try {{
                    await navigator.clipboard.writeText({safe_text_js});
                    msg.textContent = "Copied!";
                    setTimeout(() => msg.textContent = "", 2000);
                }} catch (e) {{
                    msg.style.color = "#b00020";
                    msg.textContent = "Couldn’t copy";
                    setTimeout(() => msg.textContent = "", 2500);
                }}
            }});
        </script>
    """
    components.html(html_code, height=60)

# =========================================================
# Name normalisation & near-duplicate detection utilities
# =========================================================
def strip_accents(s: str) -> str:
    """Remove accents/diacritics for more consistent comparison."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(c)
    )

def normalise_key(name: str) -> str:
    """
    Create a comparison key:
    - Lowercase
    - Trim spaces
    - Collapse multiple spaces
    - Strip accents
    """
    s = " ".join(name.strip().split())  # normalise internal whitespace
    s = strip_accents(s).lower()
    return s

def smart_capitalise_token(token: str) -> str:
    """Capitalise a token, handling apostrophes and hyphens (e.g., O'Neill, Smith-Jones)."""
    # Handle hyphenated names
    if "-" in token:
        return "-".join(smart_capitalise_token(part) for part in token.split("-"))
    # Handle apostrophes
    if "'" in token:
        return "'".join(part.capitalize() if part else "" for part in token.split("'"))
    return token.capitalize()

def smart_title(name: str) -> str:
    """
    Title-case a full name while keeping common particles lower-case
    if they are not at the start (e.g., 'van', 'de').
    """
    particles = {"de", "da", "del", "van", "von", "bin", "al", "la", "le", "di", "of", "the"}
    parts = [p for p in name.strip().split() if p]
    formatted = []
    for i, part in enumerate(parts):
        low = part.lower()
        if i > 0 and low in particles:
            formatted.append(low)
        else:
            formatted.append(smart_capitalise_token(low))
    return " ".join(formatted)

def levenshtein(a: str, b: str) -> int:
    """Classic Levenshtein edit distance."""
    if len(a) < len(b):
        a, b = b, a
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        curr = [i]
        for j, cb in enumerate(b, start=1):
            insertions = prev[j] + 1
            deletions = curr[j - 1] + 1
            substitutions = prev[j - 1] + (ca != cb)
            curr.append(min(insertions, deletions, substitutions))
        prev = curr
    return prev[-1]

def near_duplicate(a_key: str, b_key: str) -> bool:
    """
    Decide if two names are 'near duplicates' using edit distance.
    We compare keys with spaces removed to be robust to spacing.
    Adaptive threshold: allow a little more for longer names.
    """
    a_comp = a_key.replace(" ", "")
    b_comp = b_key.replace(" ", "")
    L = max(len(a_comp), len(b_comp))
    # Adaptive threshold: short names require tighter matching
    if L <= 4:
        threshold = 1
    elif L <= 8:
        threshold = 2
    else:
        threshold = 3
    return levenshtein(a_comp, b_comp) <= threshold

# =========================================================
# Entrants input with capitalisation & dedupe
# =========================================================
st.header("Entrants")
entrants = st.text_area("Enter player names (one per line):")

# Preprocess: capitalise smartly and prepare keys
raw_players = [line for line in entrants.splitlines() if line.strip()]
formatted_players = [smart_title(p) for p in raw_players]

unique_players: list[str] = []
unique_keys: list[str] = []
duplicate_messages: list[str] = []

for name in formatted_players:
    key = normalise_key(name)
    # Check exact duplicate first
    if key in unique_keys:
        # Find canonical name for message
        existing = unique_players[unique_keys.index(key)]
        duplicate_messages.append(f"{name} (duplicate of {existing})")
        continue

    # Check near-duplicates
    is_near = False
    for i, k_existing in enumerate(unique_keys):
        if near_duplicate(key, k_existing):
            existing = unique_players[i]
            duplicate_messages.append(f"{name} (similar to {existing})")
            is_near = True
            break

    if not is_near:
        unique_players.append(name)
        unique_keys.append(key)

players = unique_players

# Warning if we removed any
if duplicate_messages:
    st.warning("Duplicate or near-duplicate names removed:\n" + "\n".join(sorted(duplicate_messages)))

# Small helper text showing how many unique entrants
if raw_players:
    st.caption(f"Unique entrants: {len(players)} (from {len(raw_players)} pasted)")

# =========================================================
# Session state
# =========================================================
defaults = {
    "round": 1,
    "matches": [],
    "winners": [],
    "history": [],
    "initial_players": [],
    "round_generated": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# =========================================================
# Tournament utilities
# =========================================================
def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

def next_power_of_two(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))

def create_round(pool, round_number, initial=False):
    pool = pool[:]  # copy
    random.shuffle(pool)
    matches = []

    if round_number == 1 and initial:
        target = next_power_of_two(len(pool))
        byes_needed = target - len(pool)
        if byes_needed > 0:
            bye_players = pool[:byes_needed]
            for bp in bye_players:
                st.info(f"{bp} gets a bye in Round 1.")
                st.session_state.winners.append(bp)
            pool = pool[byes_needed:]
    else:
        if not is_power_of_two(len(pool)):
            st.error("Number of winners must be a power of 2 from Round 2 onwards.")
            return []

    for i in range(0, len(pool) - 1, 2):
        matches.append((pool[i], pool[i + 1]))
    return matches

# =========================================================
# Generate fixtures
# =========================================================
if st.button("Generate Round Fixtures"):
    if st.session_state.round == 1:
        if st.session_state.winners:
            st.session_state.matches = create_round(
                st.session_state.winners,
                round_number=1,
                initial=False
            )
            st.session_state.winners = []
        elif not players:
            st.warning("Please enter entrants first or paste results.")
        else:
            st.session_state.initial_players = players[:]
            st.session_state.matches = create_round(
                players,
                round_number=1,
                initial=True
            )
    else:
        if not st.session_state.winners:
            st.warning("No winners submitted yet.")
        elif not is_power_of_two(len(st.session_state.winners)):
            st.error(f"Number of winners is {len(st.session_state.winners)}; must be a power of 2.")
        else:
            st.session_state.matches = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.winners = []

    st.session_state.round_generated = True

# =========================================================
# Display fixtures + scoring
# =========================================================
if st.session_state.matches:
    st.header(f"Round {st.session_state.round} Fixtures")

    scores = []
    for i, (p1, p2) in enumerate(st.session_state.matches):
        st.subheader(f"Match {i + 1}: {p1} vs {p2}")
        s1 = st.number_input(f"Score for {p1}", step=1, key=f"s1_{st.session_state.round}_{i}")
        s2 = st.number_input(f"Score for {p2}", step=1, key=f"s2_{st.session_state.round}_{i}")
        scores.append((p1, p2, s1, s2))

    if st.button("Submit All Results and Redraw Next Round"):
        current_round_results = []
        for p1, p2, s1, s2 in scores:
            if s1 == s2:
                st.error(f"Tie detected in {p1} vs {p2}. Please adjust scores.")
                st.stop()
            winner = p1 if s1 > s2 else p2
            st.success(f"{p1} vs {p2} — {s1}-{s2}, Winner: {winner}")
            st.session_state.winners.append(winner)
            current_round_results.append((p1, p2, winner))

        st.session_state.history.append((st.session_state.round, current_round_results))

        if len(st.session_state.winners) == 1:
            st.success(f"🏆 Champion: {st.session_state.winners[0]}")
        elif is_power_of_two(len(st.session_state.winners)):
            st.session_state.round += 1
            st.session_state.matches = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.winners = []

# =========================================================
# Fixtures output (Google Sheets–friendly) + Copy button
# =========================================================
if st.session_state.matches:
    st.header("Copy & Paste Fixture List")

    fixture_lines = [f"{p1} vs {p2}" for p1, p2 in st.session_state.matches]
    # Force LF-only newlines for Google Sheets
    fixture_text = "\n".join(fixture_lines).replace("\r\n", "\n").replace("\r", "\n")

    st.text_area("Fixtures", fixture_text, height=140)
    clipboard_button(fixture_text)

# =========================================================
# Paste results from spreadsheet-style text
# =========================================================
st.header("Paste Spreadsheet Results")
raw_data = st.text_area("Paste each row like: Team A vs Team B = 3-1")

if st.button("Process Pasted Results"):
    lines = [line.strip() for line in raw_data.split("\n") if line.strip()]
    current_round_results = []

    for line in lines:
        try:
            match, scores_str = line.split("=")
            p1, p2 = match.split("vs")
            s1, s2 = scores_str.split("-")
            p1, p2 = p1.strip(), p2.strip()
            s1, s2 = int(s1), int(s2)

            winner = p1 if s1 > s2 else p2
            st.write(f"{p1} vs {p2} → {s1}-{s2} (Winner: {winner})")
            st.session_state.winners.append(winner)
            current_round_results.append((p1, p2, winner))
        except Exception:
            st.error(f"Could not parse line: {line}")

    if current_round_results:
        st.session_state.history.append((st.session_state.round, current_round_results))

    if len(st.session_state.winners) == 1:
        st.success(f"🏆 Champion: {st.session_state.winners[0]}")
    elif is_power_of_two(len(st.session_state.winners)):
        st.session_state.round += 1
        st.session_state.matches = create_round(
            st.session_state.winners,
            round_number=st.session_state.round,
            initial=False
        )
        st.session_state.winners = []
