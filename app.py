
import streamlit as st
import streamlit.components.v1 as components
import random
import math

st.title("Dynamic Tournament Generator 🎲")

# ------------------------------
# Copy-to-Clipboard Button (FIXED)
# ------------------------------
def clipboard_button(text_to_copy):

    # Escape problematic characters
    safe_text = text_to_copy.replace("`", "\\`")

    html_code = f"""
        <script>
            function copyToClipboard() {{
                navigator.clipboard.writeText(`{safe_text}`);
            }}
        </script>

        <button onclick="copyToClipboard()" style="
            padding: 10px 14px;
            background-color: #4CAF50;
            color: white;
            font-weight: bold;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            margin-top: 10px;
        ">
            📋 Copy Fixtures
        </button>
    """

    components.html(html_code, height=80)

# ------------------------------
# Entrants Input
# ------------------------------
st.header("Entrants")
entrants = st.text_area("Enter player names (one per line):")
players = [p.strip() for p in entrants.split("\n") if p.strip()]

# ------------------------------
# Session State Setup
# ------------------------------
defaults = {
    "round": 1,
    "matches": [],
    "winners": [],
    "history": [],
    "initial_players": [],
    "round_generated": False,
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value

# ------------------------------
# Utility Functions
# ------------------------------
def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

def next_power_of_two(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))

# ------------------------------
# Create a Round
# ------------------------------
def create_round(pool, round_number, initial=False):
    pool = pool[:]  
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
        matches.append((pool[i], pool[i+1]))

    return matches

# ------------------------------
# Generate Fixtures Button
# ------------------------------
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
            st.error("Number of winners must be a power of 2.")
        else:
            st.session_state.matches = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.winners = []

    st.session_state.round_generated = True

# ------------------------------
# Display Matches & Score Input
# ------------------------------
if st.session_state.matches:
    st.header(f"Round {st.session_state.round} Fixtures")

    scores = []
    for i, (p1, p2) in enumerate(st.session_state.matches):
        st.subheader(f"Match {i+1}: {p1} vs {p2}")
        s1 = st.number_input(f"Score for {p1}", step=1, key=f"s1_{i}")
        s2 = st.number_input(f"Score for {p2}", step=1, key=f"s2_{i}")
        scores.append((p1, p2, s1, s2))

    if st.button("Submit All Results and Redraw Next Round"):
        current_round_results = []
        for p1, p2, s1, s2 in scores:
            if s1 == s2:
                st.error(f"Tie detected in {p1} vs {p2}. Adjust scores.")
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

# ------------------------------
# Fixtures Output (Clipboard Button)
# ------------------------------
if st.session_state.matches:
    st.header("Copy & Paste Fixture List")

    fixture_lines = [f"{p1} vs {p2}" for p1, p2 in st.session_state.matches]
    fixture_text = "\n".join(fixture_lines).replace("\r\n", "\n").replace("\r", "\n")

    st.text_area("Fixtures", fixture_text, height=140)

    clipboard_button(fixture_text)

# ------------------------------
# Paste Results from Spreadsheet
# ------------------------------
st.header("Paste Spreadsheet Results")
raw_data = st.text_area("Paste each row like: Team A vs Team B = 3-1")

if st.button("Process Pasted Results"):
    lines = [line.strip() for line in raw_data.split("\n") if line.strip()]
    current_round_results = []

    for line in lines:
        try:
            match, scores = line.split("=")
            p1, p2 = match.split("vs")
            s1, s2 = scores.split("-")

            p1, p2 = p1.strip(), p2.strip()
            s1, s2 = int(s1), int(s2)

            winner = p1 if s1 > s2 else p2
            st.write(f"{p1} vs {p2} → {s1}-{s2} (Winner: {winner})")

            st.session_state.winners.append(winner)
            current_round_results.append((p1, p2, winner))

        except:
            st.error(f"Could not parse line: {line}")

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
