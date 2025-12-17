import streamlit as st
import random
import math
import graphviz

st.title("Dynamic Tournament Generator 🎲")

# --- Entrants ---
st.header("Entrants")
entrants = st.text_area("Enter player names (one per line):")
players = [p.strip() for p in entrants.split("\n") if p.strip()]

# --- Session State ---
if "round" not in st.session_state:
    st.session_state.round = 1
if "matches" not in st.session_state:
    st.session_state.matches = []
if "winners" not in st.session_state:
    st.session_state.winners = []
if "history" not in st.session_state:
    st.session_state.history = []
if "initial_players" not in st.session_state:
    st.session_state.initial_players = []
if "round_generated" not in st.session_state:
    st.session_state.round_generated = False

# --- Utilities ---
def is_power_of_two(n: int) -> bool:
    return n > 0 and (n & (n - 1)) == 0

def next_power_of_two(n: int) -> int:
    return 1 if n <= 1 else 2 ** math.ceil(math.log2(n))

# --- Round creation ---
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
            st.error("Winners count must be a power of 2 from Round 2 onward.")
            return []

    for i in range(0, len(pool) - 1, 2):
        matches.append((pool[i], pool[i+1]))
    return matches

# --- Generate Fixtures ---
if st.button("Generate Round Fixtures"):
    if st.session_state.round == 1:
        if st.session_state.winners:  # NEW: allow pasted results to act as entrants
            st.session_state.matches = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.round_generated = True
            st.session_state.winners = []
        elif not players:
            st.warning("Please enter entrants first or paste results.")
        else:
            st.session_state.initial_players = players[:]
            st.session_state.winners = []
            st.session_state.matches = create_round(players, round_number=1, initial=True)
            st.session_state.round_generated = True
    else:
        if not st.session_state.winners:
            st.warning("No winners to advance. Submit or paste match results first.")
        elif not is_power_of_two(len(st.session_state.winners)):
            st.error(f"Winners count is {len(st.session_state.winners)}; must be a power of 2.")
        else:
            st.session_state.matches = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.round_generated = True
            st.session_state.winners = []

# --- Display matches & record results interactively ---
if st.session_state.matches:
    st.header(f"Round {st.session_state.round} Fixtures")
    scores = []
    for i, (p1, p2) in enumerate(st.session_state.matches):
        st.subheader(f"Match {i+1}: {p1} vs {p2}")
        score1 = st.number_input(f"Score for {p1}", key=f"score1_{st.session_state.round}_{i}", step=1)
        score2 = st.number_input(f"Score for {p2}", key=f"score2_{st.session_state.round}_{i}", step=1)
        scores.append((p1, p2, score1, score2))

    if st.button("Submit All Results and Redraw Next Round"):
        current_round_results = []
        for p1, p2, s1, s2 in scores:
            if s1 == s2:
                st.error(f"Tie detected in {p1} vs {p2}. Please adjust scores.")
            else:
                winner = p1 if s1 > s2 else p2
                st.success(f"{p1} vs {p2} → {s1}-{s2}, Winner: {winner}")
                st.session_state.winners.append(winner)
                current_round_results.append((p1, p2, winner))
        if current_round_results:
            st.session_state.history.append((st.session_state.round, current_round_results))

        if len(st.session_state.winners) == 1:
            st.header("🏆 Champion")
            st.success(f"The champion is {st.session_state.winners[0]}!")
        elif is_power_of_two(len(st.session_state.winners)):
            st.session_state.round += 1
            st.session_state.matches = create_round(
                st.session_state.winners,
                round_number=st.session_state.round,
                initial=False
            )
            st.session_state.winners = []
            st.session_state.round_generated = True
            st.success(f"Fixtures for Round {st.session_state.round} generated automatically.")

# --- Simple text output for copy/paste ---
if st.session_state.matches:
    st.header("Copy & Paste Fixture List")
    fixture_lines = [f"{p1} vs {p2}" for p1, p2 in st.session_state.matches]
    fixture_text = "\n".join(fixture_lines)
    st.text(fixture_text)

# --- Paste Spreadsheet Data ---
st.header("Paste Spreadsheet Results")
raw_data = st.text_area("Paste rows in format: A vs B = 1-4")

if st.button("Process Pasted Results"):
    lines = [line.strip() for line in raw_data.split("\n") if line.strip()]
    current_round_results = []
    for line in lines:
        try:
            match, result = line.split("=")
            p1, p2 = match.split("vs")
            p1, p2 = p1.strip(), p2.strip()
            s1, s2 = result.strip().split("-")
            s1, s2 = int(s1), int(s2)
            winner = p1 if s1 > s2 else p2
            st.write(f"{p1} vs {p2} → {s1}-{s2}, Winner: {winner}")
            st.session_state.winners.append(winner)
            current_round_results.append((p1, p2, winner))
        except Exception:
            st.error(f"Could not parse line: {line}")
    if current_round_results:
        st.session_state.history.append((st.session_state.round, current_round_results))

    if len(st.session_state.winners) == 1:
        st.header("🏆 Champion")
        st.success(f"The champion is {st.session_state.winners[0]}!")
    elif is_power_of_two(len(st.session_state.winners)):
        st.session_state.round += 1
        st.session_state.matches = create_round(
            st.session_state.winners,
            round_number=st.session_state.round,
            initial=False
        )
        st.session_state.winners = []
        st.session_state.round_generated = True
        st.success(f"Fixtures for Round {st.session_state.round} generated automatically.")

# --- Bracket visualization ---
if st.session_state.history:
    st.header("Tournament Bracket View")
    dot = graphviz.Digraph()

    for p in st.session_state.initial_players:
        dot.node(p, p, shape="box")

    for rnd, results in st.session_state.history:
        for idx, (p1, p2, winner) in enumerate(results, start=1):
            match_id = f"R{rnd}-M{idx}"
            label = f"R{rnd} M{idx}\n{p1} vs {p2}"
            dot.node(match_id, label, shape="ellipse")
            dot.edge(p1, match_id)
            dot.edge(p2, match_id)
            dot.edge(match_id, winner)

    st.graphviz_chart(dot)
